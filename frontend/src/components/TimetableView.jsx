import React, { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || '/api/v1'

async function api(path, options = {}, auth = null) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {}),
      ...options.headers,
    },
  })
  let data = null
  try { data = await response.json() } catch { data = null }
  if (!response.ok) throw new Error(data?.detail || `Request failed (${response.status})`)
  return data
}

export function TimetableView({ auth }) {
  const [view, setView] = useState('schedule') // schedule, instructor, room, stats
  const [sessionName, setSessionName] = useState('Spring 2026')
  const [sessions, setSessions] = useState([])
  
  // Filters
  const [day, setDay] = useState('')
  const [courseCode, setCourseCode] = useState('')
  const [room, setRoom] = useState('')
  const [program, setProgram] = useState('')
  const [semester, setSemester] = useState('')
  const [instructor, setInstructor] = useState('')
  const [shift, setShift] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  
  // Data
  const [scheduleData, setScheduleData] = useState(null)
  const [instructorList, setInstructorList] = useState([])
  const [roomList, setRoomList] = useState([])
  const [stats, setStats] = useState(null)
  const [selectedInstructor, setSelectedInstructor] = useState(null)
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [searchResults, setSearchResults] = useState(null)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Load sessions on mount
  useEffect(() => {
    api('/timetable/sessions', {}, auth)
      .then(setSessions)
      .catch(() => setSessions([{ session_name: 'Spring 2026' }]))
  }, [])

  // Load initial schedule
  useEffect(() => {
    if (view === 'schedule') loadSchedule()
    else if (view === 'stats') loadStats()
  }, [view, sessionName])

  // Load instructors and rooms when needed
  useEffect(() => {
    if (view === 'instructor') {
      api('/timetable/instructors', {}, auth)
        .then(setInstructorList)
        .catch(() => {})
    } else if (view === 'room') {
      api(`/timetable/rooms?session_name=${encodeURIComponent(sessionName)}`, {}, auth)
        .then(setRoomList)
        .catch(() => {})
    }
  }, [view])

  async function loadSchedule() {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ session_name: sessionName })
      if (day) params.append('day', day)
      if (courseCode) params.append('course_code', courseCode)
      if (room) params.append('room', room)
      if (program) params.append('program', program)
      if (semester) params.append('semester', semester)
      if (instructor) params.append('instructor', instructor)
      if (shift) params.append('shift', shift)
      
      const data = await api(`/timetable/schedule?${params}`, {}, auth)
      setScheduleData(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadStats() {
    setLoading(true)
    setError('')
    try {
      const data = await api(`/timetable/stats?session_name=${encodeURIComponent(sessionName)}`, {}, auth)
      setStats(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadInstructorSchedule(instructorName) {
    setLoading(true)
    setError('')
    try {
      const data = await api(`/timetable/instructor/${encodeURIComponent(instructorName)}?session_name=${encodeURIComponent(sessionName)}`, {}, auth)
      setSelectedInstructor(data)
    } catch (e) {
      setError(e.message)
      setSelectedInstructor(null)
    } finally {
      setLoading(false)
    }
  }

  async function loadRoomSchedule(roomName) {
    setLoading(true)
    setError('')
    try {
      const data = await api(`/timetable/room/${encodeURIComponent(roomName)}?session_name=${encodeURIComponent(sessionName)}`, {}, auth)
      setSelectedRoom(data)
    } catch (e) {
      setError(e.message)
      setSelectedRoom(null)
    } finally {
      setLoading(false)
    }
  }

  async function searchSchedule() {
    if (!searchQuery.trim()) return
    setLoading(true)
    setError('')
    try {
      const data = await api(`/timetable/search?q=${encodeURIComponent(searchQuery)}&session_name=${encodeURIComponent(sessionName)}`, {}, auth)
      setSearchResults(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function clearFilters() {
    setDay('')
    setCourseCode('')
    setRoom('')
    setProgram('')
    setSemester('')
    setInstructor('')
    setShift('')
    setSearchQuery('')
    setSearchResults(null)
  }

  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
  const programs = ['BS', 'MPhil', 'PhD', 'MS-DS', 'MS-IST']
  const shifts = ['Morning', 'Afternoon', 'Evening']

  return (
    <section className="section-card full">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{sessionName} · QAU CS DEPARTMENT</p>
          <h3>Class Timetable & Schedule</h3>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <select 
            value={sessionName} 
            onChange={(e) => setSessionName(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #d1e0dd' }}
          >
            {sessions.map(s => (
              <option key={s.session_name} value={s.session_name}>{s.session_name}</option>
            ))}
          </select>
          <span className="guidance-chip">Stored schedule · confirm applicability</span>
        </div>
      </div>

      <div className="notice">This view contains stored timetable records for the selected session. Confirm the current schedule and room assignments with the department before attending.</div>

      {/* View Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '2px solid #e6f0ed', paddingBottom: '8px' }}>
        <button 
          onClick={() => setView('schedule')}
          className={view === 'schedule' ? 'tab-button active' : 'tab-button'}
          style={{
            padding: '8px 16px',
            border: 'none',
            background: view === 'schedule' ? '#1a5f57' : 'transparent',
            color: view === 'schedule' ? 'white' : '#1a5f57',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          📅 Schedule
        </button>
        <button 
          onClick={() => setView('instructor')}
          className={view === 'instructor' ? 'tab-button active' : 'tab-button'}
          style={{
            padding: '8px 16px',
            border: 'none',
            background: view === 'instructor' ? '#1a5f57' : 'transparent',
            color: view === 'instructor' ? 'white' : '#1a5f57',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          👨‍🏫 Instructors
        </button>
        <button 
          onClick={() => setView('room')}
          className={view === 'room' ? 'tab-button active' : 'tab-button'}
          style={{
            padding: '8px 16px',
            border: 'none',
            background: view === 'room' ? '#1a5f57' : 'transparent',
            color: view === 'room' ? 'white' : '#1a5f57',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          🏢 Rooms
        </button>
        <button 
          onClick={() => setView('stats')}
          className={view === 'stats' ? 'tab-button active' : 'tab-button'}
          style={{
            padding: '8px 16px',
            border: 'none',
            background: view === 'stats' ? '#1a5f57' : 'transparent',
            color: view === 'stats' ? 'white' : '#1a5f57',
            borderRadius: '8px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}
        >
          📊 Statistics
        </button>
      </div>

      {error && <div className="form-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* Schedule View */}
      {view === 'schedule' && (
        <>
          {/* Search Bar */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && searchSchedule()}
              placeholder="Search by course code, name, instructor, or room..."
              style={{ flex: 1, padding: '12px 16px', borderRadius: '8px', border: '1px solid #d1e0dd' }}
            />
            <button onClick={searchSchedule} className="primary">Search</button>
          </div>

          {/* Filters */}
          <details open style={{ marginBottom: '24px', background: '#f8fdfb', padding: '16px', borderRadius: '12px' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#1a5f57', marginBottom: '16px' }}>
              🔍 Advanced Filters
            </summary>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Day</span>
                <select value={day} onChange={(e) => setDay(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }}>
                  <option value="">All days</option>
                  {days.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Course Code</span>
                <input value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="e.g., CS-104" style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }} />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Room</span>
                <input value={room} onChange={(e) => setRoom(e.target.value)} placeholder="e.g., Room 201" style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }} />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Program</span>
                <select value={program} onChange={(e) => setProgram(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }}>
                  <option value="">All programs</option>
                  {programs.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Semester</span>
                <input value={semester} onChange={(e) => setSemester(e.target.value)} placeholder="e.g., Semester 1" style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }} />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Instructor</span>
                <input value={instructor} onChange={(e) => setInstructor(e.target.value)} placeholder="e.g., Dr. Farooq" style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }} />
              </label>

              <label style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#728c89' }}>Shift</span>
                <select value={shift} onChange={(e) => setShift(e.target.value)} style={{ padding: '8px', borderRadius: '6px', border: '1px solid #d1e0dd' }}>
                  <option value="">All shifts</option>
                  {shifts.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
              <button onClick={loadSchedule} className="primary">Apply Filters</button>
              <button onClick={clearFilters} style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #d1e0dd', background: 'white' }}>Clear All</button>
            </div>
          </details>

          {/* Search Results */}
          {searchResults && (
            <div style={{ marginBottom: '24px', background: '#f8fdfb', padding: '16px', borderRadius: '12px' }}>
              <h4 style={{ marginBottom: '12px', color: '#1a5f57' }}>
                Search Results for "{searchResults.query}" ({searchResults.results_count} found)
              </h4>
              {searchResults.results.length > 0 ? (
                <div style={{ display: 'grid', gap: '12px' }}>
                  {searchResults.results.map((entry, idx) => (
                    <ScheduleCard key={idx} entry={entry} />
                  ))}
                </div>
              ) : (
                <p style={{ color: '#728c89' }}>No results found for your search query.</p>
              )}
            </div>
          )}

          {/* Schedule Data */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '48px', color: '#728c89' }}>Loading timetable...</div>
          ) : scheduleData ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h4 style={{ color: '#1a5f57' }}>
                  {scheduleData.total_entries} Classes Found
                </h4>
                {(day || courseCode || room || program || semester || instructor || shift) && (
                  <span style={{ fontSize: '12px', color: '#728c89' }}>
                    Active filters: {[day, courseCode, room, program, semester, instructor, shift].filter(Boolean).length}
                  </span>
                )}
              </div>

              <div style={{ display: 'grid', gap: '12px' }}>
                {scheduleData.entries.map((entry) => (
                  <ScheduleCard key={entry.id} entry={entry} />
                ))}
              </div>

              {scheduleData.entries.length === 0 && (
                <div style={{ textAlign: 'center', padding: '48px', color: '#728c89' }}>
                  No classes match your filters. Try adjusting your search criteria.
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px', color: '#728c89' }}>
              Click "Apply Filters" or search to view the timetable.
            </div>
          )}
        </>
      )}

      {/* Instructor View */}
      {view === 'instructor' && (
        <>
          <h4 style={{ marginBottom: '16px', color: '#1a5f57' }}>Select an Instructor</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '12px', marginBottom: '24px' }}>
            {instructorList.filter(i => i.is_active).map((inst) => (
              <button
                key={inst.id}
                onClick={() => loadInstructorSchedule(inst.name)}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #d1e0dd',
                  background: 'white',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => e.currentTarget.style.borderColor = '#1a5f57'}
                onMouseOut={(e) => e.currentTarget.style.borderColor = '#d1e0dd'}
              >
                <div style={{ fontWeight: 'bold', color: '#1a5f57' }}>{inst.name}</div>
                <div style={{ fontSize: '12px', color: '#728c89' }}>{inst.department}</div>
              </button>
            ))}
          </div>

          {selectedInstructor && (
            <div style={{ background: '#f8fdfb', padding: '24px', borderRadius: '12px' }}>
              <h4 style={{ marginBottom: '8px', color: '#1a5f57' }}>{selectedInstructor.instructor_name}</h4>
              <p style={{ fontSize: '14px', color: '#728c89', marginBottom: '16px' }}>
                {selectedInstructor.total_classes} classes this semester
              </p>
              <div style={{ display: 'grid', gap: '12px' }}>
                {selectedInstructor.schedules.map((sched, idx) => (
                  <div key={idx} style={{ padding: '12px', background: 'white', borderRadius: '8px', border: '1px solid #d1e0dd' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 'bold', color: '#1a5f57' }}>{sched.course_code}</span>
                      <span style={{ fontSize: '12px', color: '#728c89' }}>{sched.day_of_week} • {sched.time_slot}</span>
                    </div>
                    <div style={{ fontSize: '14px', marginBottom: '4px' }}>{sched.course_name}</div>
                    <div style={{ fontSize: '12px', color: '#728c89' }}>
                      {sched.room} • {sched.program} • {sched.section_type}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Room View */}
      {view === 'room' && (
        <>
          <h4 style={{ marginBottom: '16px', color: '#1a5f57' }}>Select a Room</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px', marginBottom: '24px' }}>
            {roomList.map((r) => (
              <button
                key={r.room}
                onClick={() => loadRoomSchedule(r.room)}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #d1e0dd',
                  background: 'white',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
                onMouseOver={(e) => e.currentTarget.style.borderColor = '#1a5f57'}
                onMouseOut={(e) => e.currentTarget.style.borderColor = '#d1e0dd'}
              >
                <div style={{ fontWeight: 'bold', fontSize: '18px', color: '#1a5f57', marginBottom: '4px' }}>{r.room}</div>
                <div style={{ fontSize: '12px', color: '#728c89' }}>{r.class_count} classes</div>
                <div style={{ fontSize: '10px', color: '#728c89', marginTop: '4px' }}>{r.shifts_used.join(', ')}</div>
              </button>
            ))}
          </div>

          {selectedRoom && (
            <div style={{ background: '#f8fdfb', padding: '24px', borderRadius: '12px' }}>
              <h4 style={{ marginBottom: '8px', color: '#1a5f57' }}>{selectedRoom.room}</h4>
              <p style={{ fontSize: '14px', color: '#728c89', marginBottom: '16px' }}>
                {selectedRoom.total_slots} time slots utilized
              </p>
              <div style={{ display: 'grid', gap: '12px' }}>
                {selectedRoom.schedules.map((sched, idx) => (
                  <div key={idx} style={{ padding: '12px', background: 'white', borderRadius: '8px', border: '1px solid #d1e0dd' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 'bold', color: '#1a5f57' }}>{sched.course_code}</span>
                      <span style={{ fontSize: '12px', color: '#728c89' }}>{sched.day_of_week} • {sched.time_slot}</span>
                    </div>
                    <div style={{ fontSize: '14px', marginBottom: '4px' }}>{sched.course_name}</div>
                    <div style={{ fontSize: '12px', color: '#728c89' }}>
                      {sched.instructors.join(', ')} • {sched.program}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Statistics View */}
      {view === 'stats' && loading && (
        <div style={{ textAlign: 'center', padding: '48px', color: '#728c89' }}>Loading statistics...</div>
      )}

      {view === 'stats' && stats && !loading && (
        <div style={{ display: 'grid', gap: '24px' }}>
          {/* Summary Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <StatCard title="Total Classes" value={stats.statistics.total_schedule_entries} icon="📚" />
            <StatCard title="Unique Courses" value={stats.statistics.unique_courses} icon="🎓" />
            <StatCard title="Instructors" value={stats.statistics.instructors_count} icon="👨‍🏫" />
            <StatCard title="Rooms Used" value={stats.statistics.rooms_used} icon="🏢" />
            <StatCard title="Morning Classes" value={stats.statistics.morning_classes} icon="🌅" />
            <StatCard title="Afternoon Classes" value={stats.statistics.afternoon_classes} icon="☀️" />
            <StatCard title="Evening Classes" value={stats.statistics.evening_classes} icon="🌙" />
            <StatCard title="Programs" value={stats.statistics.programs_count} icon="📋" />
          </div>

          {/* Day Breakdown */}
          <div style={{ background: '#f8fdfb', padding: '24px', borderRadius: '12px' }}>
            <h4 style={{ marginBottom: '16px', color: '#1a5f57' }}>Classes by Day</h4>
            <div style={{ display: 'grid', gap: '12px' }}>
              {stats.by_day.map((d) => (
                <div key={d.day_of_week} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ width: '120px', fontWeight: 'bold', color: '#1a5f57' }}>{d.day_of_week}</div>
                  <div style={{ flex: 1, height: '24px', background: '#e6f0ed', borderRadius: '12px', overflow: 'hidden' }}>
                    <div 
                      style={{ 
                        height: '100%', 
                        background: '#1a5f57', 
                        width: `${(d.class_count / Math.max(...stats.by_day.map(x => x.class_count))) * 100}%`,
                        transition: 'width 0.3s'
                      }} 
                    />
                  </div>
                  <div style={{ width: '60px', textAlign: 'right', fontWeight: 'bold', color: '#1a5f57' }}>{d.class_count}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function ScheduleCard({ entry }) {
  return (
    <div style={{ 
      padding: '16px', 
      background: 'white', 
      borderRadius: '12px', 
      border: '1px solid #d1e0dd',
      transition: 'all 0.2s'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
        <div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
            <span style={{ fontWeight: 'bold', fontSize: '16px', color: '#1a5f57' }}>{entry.course_code}</span>
            <span style={{ fontSize: '12px', padding: '2px 8px', background: '#e6f0ed', borderRadius: '4px', color: '#1a5f57' }}>
              {entry.section_type}
            </span>
          </div>
          <div style={{ fontSize: '14px', color: '#2d3436', marginBottom: '4px' }}>{entry.course_name}</div>
          <div style={{ fontSize: '12px', color: '#728c89' }}>{entry.credit_hours} credit hours</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#1a5f57' }}>{entry.day_of_week}</div>
          <div style={{ fontSize: '12px', color: '#728c89' }}>{entry.time_slot}</div>
          <div style={{ fontSize: '12px', padding: '2px 6px', background: '#f8fdfb', borderRadius: '4px', marginTop: '4px' }}>
            {entry.shift}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', paddingTop: '12px', borderTop: '1px solid #e6f0ed' }}>
        <div>
          <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#728c89', marginBottom: '4px' }}>ROOM</div>
          <div style={{ fontSize: '13px', color: '#1a5f57' }}>{entry.room}</div>
        </div>
        <div>
          <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#728c89', marginBottom: '4px' }}>PROGRAM</div>
          <div style={{ fontSize: '13px', color: '#1a5f57' }}>{entry.program} • {entry.semester}</div>
        </div>
      </div>

      {entry.instructors && entry.instructors.length > 0 && (
        <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid #e6f0ed' }}>
          <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#728c89', marginBottom: '4px' }}>INSTRUCTOR(S)</div>
          <div style={{ fontSize: '13px', color: '#1a5f57' }}>{entry.instructors.join(', ')}</div>
        </div>
      )}

      {entry.teaching_assistants && entry.teaching_assistants.length > 0 && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontSize: '10px', fontWeight: 'bold', color: '#728c89', marginBottom: '4px' }}>TA(S)</div>
          <div style={{ fontSize: '13px', color: '#728c89' }}>{entry.teaching_assistants.join(', ')}</div>
        </div>
      )}
    </div>
  )
}

function StatCard({ title, value, icon }) {
  return (
    <div style={{ 
      padding: '20px', 
      background: 'white', 
      borderRadius: '12px', 
      border: '1px solid #d1e0dd',
      textAlign: 'center'
    }}>
      <div style={{ fontSize: '32px', marginBottom: '8px' }}>{icon}</div>
      <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1a5f57', marginBottom: '4px' }}>{value}</div>
      <div style={{ fontSize: '12px', color: '#728c89' }}>{title}</div>
    </div>
  )
}
