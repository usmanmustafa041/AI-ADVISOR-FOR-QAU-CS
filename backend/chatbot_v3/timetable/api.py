import asyncio
from contextlib import suppress
from urllib.parse import unquote

from app.core.auth import admin_user
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from chatbot_v3.timetable.contracts import (
    CurrentTerm,
    PublishAction,
    ReviewAction,
    RowEdit,
    TimetableQuery,
    UploadMetadata,
)
from chatbot_v3.timetable.query import execute, render
from chatbot_v3.timetable.store import MAX_BYTES, TimetableStore


class TimetableJobs:
    def __init__(self, store):
        self.store = store
        self.queue = asyncio.Queue(maxsize=100)
        self.worker = None

    async def start(self):
        self.worker = asyncio.create_task(self.run())
        for version in self.store.recover_jobs():
            await self.queue.put(version)

    async def run(self):
        while True:
            version = await self.queue.get()
            try:
                await asyncio.to_thread(self.store.parse, version)
            finally:
                self.queue.task_done()

    async def close(self):
        self.worker.cancel()
        with suppress(asyncio.CancelledError):
            await self.worker


def install(app):
    router = APIRouter(prefix="/api/v3")

    def store(request: Request):
        return request.app.state.timetables

    @router.get("/admin/timetables/versions")
    def versions(s=Depends(store), user=Depends(admin_user)):
        return s.versions()

    @router.post("/admin/timetables/versions", status_code=202)
    async def upload(request: Request, s=Depends(store), user=Depends(admin_user)):
        if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
            raise HTTPException(415, "Upload with application/pdf")
        try:
            metadata = UploadMetadata.model_validate_json(
                unquote(request.headers.get("x-timetable-metadata", ""))
            )
            if request.app.state.timetable_jobs.queue.full():
                raise HTTPException(503, "Extraction queue is full; retry later")
            data = await request.body()
            if len(data) > MAX_BYTES:
                raise HTTPException(413, "PDF exceeds 20 MiB")
            version, created = await asyncio.to_thread(
                s.upload,
                data,
                unquote(request.headers.get("x-filename", "timetable.pdf")),
                metadata,
                str(user["id"]),
            )
            if created:
                await request.app.state.timetable_jobs.queue.put(version)
            return {"version_id": version, "created": created, "preview_only": True}
        except ValueError as e:
            raise HTTPException(422, str(e)) from None

    @router.get("/admin/timetables/versions/{version}")
    def detail(version: str, s=Depends(store), user=Depends(admin_user)):
        return s.detail(version)

    @router.get("/admin/timetables/versions/{version}/pdf")
    def pdf(version: str, s=Depends(store), user=Depends(admin_user)):
        v = s.version(version)
        return FileResponse(
            v["path"],
            media_type="application/pdf",
            filename=v["filename"],
            content_disposition_type="inline",
            headers={
                "Content-Security-Policy": "sandbox",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )

    @router.get("/admin/timetables/versions/{version}/pages/{page}")
    def page_image(version: str, page: int, s=Depends(store), user=Depends(admin_user)):
        import pdfplumber

        v = s.version(version)
        if not 1 <= page <= v["pages"]:
            raise HTTPException(404)
        target = s.root / "previews" / f"{version}-{page}.png"
        target.parent.mkdir(exist_ok=True)
        if not target.exists():
            with pdfplumber.open(v["path"]) as doc:
                doc.pages[page - 1].to_image(resolution=100).save(target)
        return FileResponse(
            target, media_type="image/png", headers={"Cache-Control": "private, no-store"}
        )

    @router.patch("/admin/timetables/versions/{version}/meetings/{meeting}")
    def edit(version: str, meeting: str, body: RowEdit, s=Depends(store), user=Depends(admin_user)):
        s.edit(version, meeting, body, str(user["id"]))
        return s.detail(version)

    @router.post("/admin/timetables/versions/{version}/issues/{issue}/resolve")
    def resolve(
        version: str, issue: str, body: ReviewAction, s=Depends(store), user=Depends(admin_user)
    ):
        s.resolve(version, issue, body, str(user["id"]))
        return s.detail(version)

    @router.patch("/admin/timetables/versions/{version}/offerings/{offering}")
    def edit_offering(
        version: str, offering: str, body: RowEdit, s=Depends(store), user=Depends(admin_user)
    ):
        s.edit_offering(version, offering, body, str(user["id"]))
        return s.detail(version)

    @router.post("/admin/timetables/versions/{version}/publish")
    def publish(version: str, body: PublishAction, s=Depends(store), user=Depends(admin_user)):
        return s.publish(version, body, str(user["id"]))

    @router.post("/admin/timetables/versions/{version}/rollback")
    def rollback(version: str, body: PublishAction, s=Depends(store), user=Depends(admin_user)):
        return s.publish(version, body, str(user["id"]), rollback=True)

    @router.post("/admin/timetables/versions/{version}/reextract", status_code=202)
    async def reextract(
        version: str,
        body: ReviewAction,
        request: Request,
        s=Depends(store),
        user=Depends(admin_user),
    ):
        if request.app.state.timetable_jobs.queue.full():
            raise HTTPException(503, "Extraction queue is full")
        before = s.detail(version)
        with s.connect(write=True) as c:
            v = s.version(version, c)
            if v["status"] == "failed" and v["revision"] == body.expected_revision:
                pass
            else:
                s.editable(c, version, body.expected_revision)
            s.audit(
                c,
                str(user["id"]),
                "reextract",
                version,
                {"reason": body.reason, "previous_preview": before},
            )
            c.execute(
                "DELETE FROM tt_meeting_course WHERE meeting_id IN (SELECT id FROM tt_meeting WHERE version_id=?)",
                (version,),
            )
            c.execute(
                "DELETE FROM tt_teacher_assignment WHERE offering_id IN (SELECT id FROM tt_offering WHERE version_id=?)",
                (version,),
            )
            for table in ("tt_issue", "tt_meeting", "tt_offering"):
                c.execute(f"DELETE FROM {table} WHERE version_id=?", (version,))
            c.execute(
                "UPDATE tt_version SET status='queued',revision=revision+1 WHERE id=?", (version,)
            )
        await request.app.state.timetable_jobs.queue.put(version)
        return {"version_id": version, "status": "queued"}

    @router.post("/admin/timetables/current-term")
    def current_term(body: CurrentTerm, s=Depends(store), user=Depends(admin_user)):
        with s.connect(write=True) as c:
            c.execute(
                "INSERT INTO tt_current_term VALUES(?,?,?,?,?) ON CONFLICT(department,campus) DO UPDATE SET academic_term=excluded.academic_term,valid_from=excluded.valid_from,valid_until=excluded.valid_until",
                (
                    body.department,
                    body.campus,
                    body.academic_term,
                    str(body.valid_from),
                    str(body.valid_until),
                ),
            )
            s.audit(c, str(user["id"]), "set_current_term", None, body.model_dump(mode="json"))
        return body

    @router.post("/timetables/query")
    def query(body: TimetableQuery, s=Depends(store)):
        result = execute(s, body)
        answer, refs = render(result)
        return result | {"answer": answer, "cited_sources": [r.model_dump() for r in refs]}

    @router.get("/timetables/versions/{version}/pdf")
    def published_pdf(version: str, s=Depends(store)):
        v = s.version(version)
        if v["status"] not in {"published", "archived"}:
            raise HTTPException(404, "Published source not found")
        return FileResponse(
            v["path"],
            media_type="application/pdf",
            filename=v["filename"],
            content_disposition_type="inline",
            headers={
                "Content-Security-Policy": "sandbox",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    app.include_router(router)


async def start(app):
    app.state.timetables = TimetableStore()
    app.state.timetable_jobs = TimetableJobs(app.state.timetables)
    await app.state.timetable_jobs.start()
