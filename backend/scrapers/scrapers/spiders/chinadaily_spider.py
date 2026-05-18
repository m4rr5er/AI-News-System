import scrapy
from datetime import datetime
from scrapers.items import NewsItem
import re
import json


class ChinaDailySpider(scrapy.Spider):
    """Spider for crawling China Daily English news website"""

    name = "chinadaily"
    allowed_domains = ["chinadaily.com.cn"]

    # China Daily main sections
    start_urls = [
        "https://www.chinadaily.com.cn/business",           # Business
        "https://www.chinadaily.com.cn/culture",            # Culture
        "https://www.chinadaily.com.cn/travel",             # Travel
        "https://www.chinadaily.com.cn/sports",             # Sport
        "https://www.chinadaily.com.cn/business/tech",      # Technology
        "https://www.chinadaily.com.cn/china/environment",  # Environment
        "https://www.chinadaily.com.cn/china/59b8d010a3108c54ed7dfc27",  # Health
        "https://www.chinadaily.com.cn/culture/art",        # Arts
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 1.5,
    }

    def parse(self, response):
        """Parse category pages to extract article links"""
        self.logger.info(f"Parsing page: {response.url}")

        # Extract category from URL
        category = self.extract_category(response.url)

        # China Daily article links - they use protocol-relative URLs like //www.chinadaily.com.cn/a/...
        article_links = []

        # Primary method: Find all links containing "/a/" (China Daily article pattern)
        article_links += response.css('a[href*="/a/"]::attr(href)').getall()

        # Backup methods for other possible patterns
        article_links += response.css('div.mb10 a::attr(href)').getall()
        article_links += response.css('div.tw3_01_2b a::attr(href)').getall()
        article_links += response.css('div.tw3_01_2c a::attr(href)').getall()
        article_links += response.css('a.tw_link::attr(href)').getall()
        article_links += response.css('ul.list_009 a::attr(href)').getall()

        # Remove duplicates
        article_links = list(set(article_links))

        self.logger.info(f"Found {len(article_links)} article links on {response.url}")

        # Follow article links
        for link in article_links:
            if self.is_valid_article_url(link):
                # Handle protocol-relative URLs (//www.chinadaily.com.cn/...)
                if link.startswith('//'):
                    link = 'https:' + link

                full_url = response.urljoin(link)
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_article,
                    meta={'category': category},
                    errback=self.handle_error
                )

    def parse_article(self, response):
        """Parse individual article page to extract content"""
        self.logger.info(f"Parsing article: {response.url}")

        # Extract title
        title = None

        # Method 1: Standard h1
        title = response.css('h1::text').get()

        # Method 2: Title with specific class
        if not title:
            title = response.css('h1.title::text').get()

        # Method 3: Meta og:title
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get()

        # Method 4: Title in info area
        if not title:
            title = response.css('div.info_l h1::attr(title)').get()

        # Method 5: Concatenate h1 text nodes
        if not title:
            title_parts = response.css('h1 *::text').getall()
            if title_parts:
                title = ' '.join(title_parts).strip()

        if not title:
            self.logger.warning(f"No title found for {response.url}")
            return

        # Extract article content
        content_paragraphs = []

        # Method 1: Main article content div (get all text including nested elements)
        for p in response.css('div#Content p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 2: Article body
        if not content_paragraphs:
            for p in response.css('div.article_content p, div.article p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 3: Content with specific IDs
        if not content_paragraphs:
            for p in response.css('div#p_content p, div#content p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 4: TRS editor content (China Daily uses TRS CMS)
        if not content_paragraphs:
            for p in response.css('div.TRS_Editor p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 5: Generic article paragraphs
        if not content_paragraphs:
            for p in response.css('article p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 6: Paragraph with specific classes
        if not content_paragraphs:
            for p in response.css('p.content'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Remove duplicates while preserving order
        seen = set()
        unique_paragraphs = []
        for p in content_paragraphs:
            # Filter out very short paragraphs and common non-content text
            if (p and
                len(p) > 20 and
                p not in seen and
                not p.startswith('•') and
                'Subscribe' not in p and
                'Contact us' not in p and
                'Copyright' not in p):
                seen.add(p)
                unique_paragraphs.append(p)

        # Join content with newlines to preserve paragraph structure
        content = '\n\n'.join(unique_paragraphs)

        if not content or len(content) < 100:
            self.logger.warning(f"Insufficient content found for {response.url} (length: {len(content)})")
            return

        # Extract publish date
        publish_date = self.extract_publish_date(response)

        # Extract cover image (first image in article)
        cover_image = self.extract_cover_image(response)

        # Create news item
        item = NewsItem()
        item['title'] = title.strip()
        item['content'] = content
        item['cover_image'] = cover_image
        item['url'] = response.url
        item['source'] = 'China Daily'
        item['publish_date'] = publish_date
        item['crawl_date'] = datetime.now()
        item['category'] = response.meta.get('category', 'general')

        yield item

    def extract_category(self, url):
        """Extract category from URL"""
        # Check for specific category URLs first (more specific patterns first)
        if '/business/tech' in url:
            return 'Technology'
        elif '/culture/art' in url:
            return 'Arts'
        elif '/china/environment' in url or '/environment' in url or '/green' in url:
            return 'Environment'
        elif '59b8d010a3108c54ed7dfc27' in url:  # Health section ID
            return 'Health'
        elif '/business' in url or '/bizchina' in url:
            return 'Business'
        elif '/culture' in url:
            return 'Culture'
        elif '/travel' in url:
            return 'Travel'
        elif '/sports' in url:
            return 'Sport'
        else:
            return 'general'

    def is_valid_article_url(self, url):
        """Check if URL is a valid China Daily article"""
        if not url:
            return False

        # Must be China Daily domain or relative URL
        if 'chinadaily.com.cn' not in url and not url.startswith('/'):
            return False

        # China Daily article URLs typically have these patterns:
        # Pattern 1: /a/YYYYMM/DD/WS[id].html
        # Pattern 2: /china/YYYY-MM/DD/content_[id].htm
        # Pattern 3: /[section]/YYYY-MM/DD/content_[id].htm

        valid_patterns = [
            r'/a/\d{6}/\d{2}/WS[a-zA-Z0-9]+\.html',  # /a/202401/15/WS123abc.html
            r'/\w+/\d{4}-\d{2}/\d{2}/content_\d+\.htm',  # /china/2024-01/15/content_123.htm
            r'/articles/\d+/\d+/\d+/[a-zA-Z0-9]+\.html',  # /articles/2024/01/15/article.html
        ]

        for pattern in valid_patterns:
            if re.search(pattern, url):
                # Exclude non-article pages
                exclude_patterns = [
                    '/video/',
                    '/photo/',
                    '/gallery/',
                    '/multimedia/',
                    '/pdf/',
                    '/epaper/',
                    '/kindle/',
                    '/mobile/',
                    '/rss/',
                    '/sitemap/',
                    '/about/',
                    '/contact/',
                    '/subscribe/',
                ]

                for exclude in exclude_patterns:
                    if exclude in url.lower():
                        return False

                return True

        return False

    def extract_publish_date(self, response):
        """Extract publish date from article page"""
        # Method 1: Meta tag article:published_time
        date_meta = response.css('meta[property="article:published_time"]::attr(content)').get()
        if date_meta:
            try:
                return datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
            except:
                pass

        # Method 2: Meta tag og:published_time
        date_meta = response.css('meta[property="og:published_time"]::attr(content)').get()
        if date_meta:
            try:
                return datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
            except:
                pass

        # Method 3: JSON-LD structured data
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for script in scripts:
            try:
                data = json.loads(script)
                if isinstance(data, dict) and 'datePublished' in data:
                    date_str = data['datePublished']
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                continue

        # Method 4: Time element with datetime attribute
        time_element = response.css('time::attr(datetime)').get()
        if time_element:
            try:
                return datetime.fromisoformat(time_element.replace('Z', '+00:00'))
            except:
                pass

        # Method 5: Specific China Daily date span/div
        date_text = response.css('span.info_l::text').get()
        if not date_text:
            date_text = response.css('div.info_l::text').get()
        if not date_text:
            date_text = response.css('span.date::text').get()
        if not date_text:
            date_text = response.css('div.date::text').get()

        if date_text:
            try:
                # Try to parse various date formats
                # Format: "2024-01-15 10:30" or "Jan 15, 2024"
                date_text = date_text.strip()

                # Try ISO format first
                if re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                    date_part = date_text.split()[0]
                    return datetime.strptime(date_part, '%Y-%m-%d')
            except:
                pass

        # Method 6: Extract from URL
        # Pattern: /a/YYYYMM/DD/ or /YYYY-MM/DD/
        date_match = re.search(r'/a/(\d{4})(\d{2})/(\d{2})/', response.url)
        if date_match:
            try:
                year, month, day = date_match.groups()
                return datetime(int(year), int(month), int(day))
            except:
                pass

        date_match = re.search(r'/(\d{4})-(\d{2})/(\d{2})/', response.url)
        if date_match:
            try:
                year, month, day = date_match.groups()
                return datetime(int(year), int(month), int(day))
            except:
                pass

        # Default to current date if not found
        return datetime.now()

    def extract_cover_image(self, response):
        """Extract the first image from the article as cover image"""
        # Method 1: Try to get image from article body
        images = response.css('article img::attr(src)').getall()

        # Method 2: Try Content div images
        if not images:
            images = response.css('div#Content img::attr(src)').getall()

        # Method 3: Try article content images
        if not images:
            images = response.css('div.article_content img::attr(src)').getall()

        # Method 4: Try figure elements
        if not images:
            images = response.css('figure img::attr(src)').getall()

        # Method 5: Try picture elements
        if not images:
            images = response.css('picture img::attr(src)').getall()

        # Method 6: Try TRS editor images
        if not images:
            images = response.css('div.TRS_Editor img::attr(src)').getall()

        # Method 7: Try og:image meta tag as fallback
        if not images:
            og_image = response.css('meta[property="og:image"]::attr(content)').get()
            if og_image:
                images = [og_image]

        # Filter out small icons, logos, and invalid images
        for img_url in images:
            if img_url and self.is_valid_cover_image(img_url):
                # Handle protocol-relative URLs
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url

                # Convert relative URLs to absolute
                full_url = response.urljoin(img_url)
                return full_url

        # Return None if no valid image found
        return None

    def is_valid_cover_image(self, url):
        """Check if the image URL is valid for use as cover image"""
        if not url:
            return False

        # Exclude small icons, logos, and tracking pixels
        exclude_patterns = [
            'icon',
            'logo',
            'avatar',
            'pixel',
            'tracking',
            '1x1',
            'placeholder',
            'sprite',
            'badge',
            'button',
        ]

        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Must be a valid image format
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if not any(ext in url_lower for ext in valid_extensions):
            # China Daily images might not have extensions in URL, check for China Daily image domains
            if 'chinadaily.com.cn' not in url_lower:
                return False

        return True

    def handle_error(self, failure):
        """Handle request errors"""
        self.logger.error(f"Request failed: {failure.request.url}")
        self.logger.error(f"Error: {failure.value}")
