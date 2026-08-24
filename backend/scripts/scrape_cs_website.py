"""
Complete CS Department Website Scraper
Scrapes ALL pages from cs.qau.edu.pk and stores in structured format for RAG
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse
from pathlib import Path
import hashlib

class CSWebsiteScraper:
    def __init__(self, base_url="https://cs.qau.edu.pk"):
        self.base_url = base_url
        self.visited_urls = set()
        self.scraped_data = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Academic Research Bot)'
        })
    
    def is_valid_url(self, url):
        """Check if URL belongs to CS department site"""
        parsed = urlparse(url)
        return parsed.netloc in ['cs.qau.edu.pk', 'www.cs.qau.edu.pk']
    
    def extract_text_content(self, soup):
        """Extract meaningful text from page"""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return '\n'.join(lines)
    
    def extract_links(self, soup, current_url):
        """Extract all internal links"""
        links = set()
        for link in soup.find_all('a', href=True):
            url = urljoin(current_url, link['href'])
            if self.is_valid_url(url):
                # Remove fragments
                url = url.split('#')[0]
                links.add(url)
        return links
    
    def scrape_page(self, url):
        """Scrape single page"""
        if url in self.visited_urls:
            return set()
        
        print(f"Scraping: {url}")
        self.visited_urls.add(url)
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract page data
            title = soup.find('title')
            title_text = title.get_text().strip() if title else url
            
            # Extract main content
            content = self.extract_text_content(soup)
            
            # Store page data
            page_data = {
                'url': url,
                'title': title_text,
                'content': content,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'content_hash': hashlib.md5(content.encode()).hexdigest(),
                'word_count': len(content.split())
            }
            
            self.scraped_data.append(page_data)
            
            # Find new links
            links = self.extract_links(soup, url)
            return links - self.visited_urls
            
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return set()
        
        finally:
            time.sleep(0.5)  # Be respectful
    
    def scrape_all(self, start_url=None):
        """Scrape entire website starting from homepage"""
        if start_url is None:
            start_url = self.base_url
        
        to_visit = {start_url}
        
        # Key pages to ensure we visit
        priority_pages = [
            f"{self.base_url}/",
            f"{self.base_url}/academics.php",
            f"{self.base_url}/admissions.php",
            f"{self.base_url}/bs.html",
            f"{self.base_url}/ms_ds.php",
            f"{self.base_url}/mphil.php",
            f"{self.base_url}/phd.php",
            f"{self.base_url}/faculty.php",
            f"{self.base_url}/research.php",
        ]
        
        to_visit.update(priority_pages)
        
        while to_visit:
            url = to_visit.pop()
            new_links = self.scrape_page(url)
            to_visit.update(new_links)
            
            # Limit to avoid infinite loops
            if len(self.visited_urls) > 100:
                print("Reached page limit, stopping...")
                break
        
        print(f"\nCompleted! Scraped {len(self.scraped_data)} pages")
        return self.scraped_data
    
    def save_to_json(self, output_file):
        """Save scraped data to JSON file"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.scraped_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(self.scraped_data)} pages to {output_file}")
    
    def save_for_rag(self, output_dir):
        """Save in RAG-friendly format (one file per page)"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for idx, page in enumerate(self.scraped_data):
            filename = f"page_{idx:03d}_{page['content_hash'][:8]}.json"
            with open(output_path / filename, 'w', encoding='utf-8') as f:
                json.dump(page, f, indent=2, ensure_ascii=False)
        
        # Create index
        index = {
            'total_pages': len(self.scraped_data),
            'pages': [
                {
                    'id': idx,
                    'url': page['url'],
                    'title': page['title'],
                    'word_count': page['word_count'],
                    'filename': f"page_{idx:03d}_{page['content_hash'][:8]}.json"
                }
                for idx, page in enumerate(self.scraped_data)
            ]
        }
        
        with open(output_path / 'index.json', 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(self.scraped_data)} pages to {output_dir}/")


if __name__ == "__main__":
    scraper = CSWebsiteScraper()
    
    print("Starting CS Department Website Scraper...")
    print("=" * 60)
    
    # Scrape all pages
    data = scraper.scrape_all()
    
    # Save in multiple formats
    scraper.save_to_json('academic-data/scraped/cs_website_full.json')
    scraper.save_for_rag('academic-data/scraped/pages')
    
    print("\n" + "=" * 60)
    print("✅ Scraping Complete!")
    print(f"Total pages scraped: {len(data)}")
    print(f"Total words: {sum(p['word_count'] for p in data)}")
