import scrapy
from datetime import datetime
from scrapers.items import NewsItem
import re
import json


class CNNSpider(scrapy.Spider):
    """Spider for crawling CNN with dynamic content loading support"""

    name = "cnn"
    allowed_domains = ["cnn.com"]

    # CNN main sections
    start_urls = [
        "https://edition.cnn.com/politics",
        "https://edition.cnn.com/business",
        "https://edition.cnn.com/health",
        "https://edition.cnn.com/entertainment",
        "https://edition.cnn.com/travel",
        "https://edition.cnn.com/sport",
        "https://edition.cnn.com/science",
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2,  # Slower for CNN to avoid blocking
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        # Enable JavaScript rendering if Splash is available
        # 'SPLASH_URL': 'http://localhost:8050',
        # 'DOWNLOADER_MIDDLEWARES': {
        #     'scrapy_splash.SplashCookiesMiddleware': 723,
        #     'scrapy_splash.SplashMiddleware': 725,
        #     'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
        # },
        # 'SPIDER_MIDDLEWARES': {
        #     'scrapy_splash.SplashDeduplicateArgsMiddleware': 100,
        # },
    }

    def parse(self, response):
        """Parse category pages to extract article links"""
        self.logger.info(f"Parsing page: {response.url}")

        # Extract category from URL
        category = self.extract_category(response.url)

        # CNN uses various selectors for article links
        article_links = []

        # Method 1: Links in card containers
        article_links += response.css('a.container__link::attr(href)').getall()

        # Method 2: Links with specific CNN article patterns
        article_links += response.css('a[href*="/2024/"], a[href*="/2025/"], a[href*="/2026/"]::attr(href)').getall()

        # Method 3: Links in article containers
        article_links += response.css('article a::attr(href)').getall()

        # Method 4: Links in headline containers
        article_links += response.css('h3.cd__headline a::attr(href)').getall()
        article_links += response.css('span.cd__headline-text a::attr(href)').getall()

        # Method 5: Data-zjs links (CNN's dynamic content)
        article_links += response.css('a[data-zjs]::attr(href)').getall()

        # Method 6: Extract from JSON-LD or embedded data
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for script in scripts:
            try:
                data = json.loads(script)
                if isinstance(data, dict):
                    # Extract URLs from structured data
                    if 'url' in data:
                        article_links.append(data['url'])
                    if '@graph' in data:
                        for item in data['@graph']:
                            if isinstance(item, dict) and 'url' in item:
                                article_links.append(item['url'])
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'url' in item:
                            article_links.append(item['url'])
            except:
                continue

        # Remove duplicates
        article_links = list(set(article_links))

        self.logger.info(f"Found {len(article_links)} article links on {response.url}")

        # Follow article links
        for link in article_links:
            if self.is_valid_article_url(link):
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

        # Method 1: Standard h1 title
        title = response.css('h1.headline__text::text').get()

        # Method 2: Alternative title selectors
        if not title:
            title = response.css('h1[data-editable="headlineText"]::text').get()

        # Method 3: Meta title
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get()

        # Method 4: Any h1
        if not title:
            title = response.css('h1::text').get()

        if not title:
            self.logger.warning(f"No title found for {response.url}")
            return

        # Extract article content
        content_paragraphs = []

        # Method 1: Main article body paragraphs (get all text including nested elements)
        for p in response.css('div.article__content p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 2: Paragraph containers
        if not content_paragraphs:
            for p in response.css('div[class*="paragraph"] p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 3: Body text paragraphs
        if not content_paragraphs:
            for elem in response.css('div.body__paragraph, p.paragraph'):
                text = ''.join(elem.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 4: Zephr paragraphs (CNN's content system)
        if not content_paragraphs:
            for elem in response.css('div[data-editable="text"] p, div.zn-body__paragraph'):
                text = ''.join(elem.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 5: Generic article paragraphs
        if not content_paragraphs:
            for p in response.css('article p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 6: Try to extract from structured data
        if not content_paragraphs:
            article_body = response.css('meta[property="og:description"]::attr(content)').get()
            if article_body:
                content_paragraphs.append(article_body.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_paragraphs = []
        for p in content_paragraphs:
            # Filter out very short paragraphs (likely navigation text)
            if p and len(p) > 20 and p not in seen:
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
        item['source'] = 'CNN'
        item['publish_date'] = publish_date
        item['crawl_date'] = datetime.now()
        item['category'] = response.meta.get('category', 'general')

        yield item

    def extract_category(self, url):
        """Extract category from URL"""
        if '/politics' in url:
            return 'Politics'
        elif '/business' in url:
            return 'Business'
        elif '/health' in url:
            return 'Health'
        elif '/entertainment' in url:
            return 'Entertainment'
        elif '/travel' in url:
            return 'Travel'
        elif '/sport' in url:
            return 'Sport'
        elif '/science' in url:
            return 'Science'
        else:
            return 'General'

    def is_valid_article_url(self, url):
        """Check if URL is a valid CNN article"""
        if not url:
            return False

        # Must be CNN domain
        if 'cnn.com' not in url and not url.startswith('/'):
            return False

        # CNN article URLs typically contain year in path
        if not re.search(r'/202[0-9]/', url):
            return False

        # Exclude non-article pages
        exclude_patterns = [
            '/video/',
            '/videos/',
            '/live-news/',
            '/gallery/',
            '/interactive/',
            '/specials/',
            '/profiles/',
            '/author/',
            '/newsletters/',
            '/audio/',
            '/podcasts/',
            'cnn.com/cnn-underscored',
            'cnn.com/coupons',
        ]

        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False

        # Valid article URLs should have reasonable length
        if len(url) < 20:
            return False

        return True

    def extract_publish_date(self, response):
        """Extract publish date from article page"""
        # Method 1: Meta tag article:published_time
        date_meta = response.css('meta[property="article:published_time"]::attr(content)').get()
        if date_meta:
            try:
                return datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
            except:
                pass

        # Method 2: JSON-LD structured data
        scripts = response.css('script[type="application/ld+json"]::text').getall()
        for script in scripts:
            try:
                data = json.loads(script)
                if isinstance(data, dict):
                    if 'datePublished' in data:
                        date_str = data['datePublished']
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if '@graph' in data:
                        for item in data['@graph']:
                            if isinstance(item, dict) and 'datePublished' in item:
                                date_str = item['datePublished']
                                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                continue

        # Method 3: Meta tag og:article:published_time
        date_meta = response.css('meta[property="og:article:published_time"]::attr(content)').get()
        if date_meta:
            try:
                return datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
            except:
                pass

        # Method 4: Time element
        time_element = response.css('time::attr(datetime)').get()
        if time_element:
            try:
                return datetime.fromisoformat(time_element.replace('Z', '+00:00'))
            except:
                pass

        # Method 5: Extract from URL (CNN URLs contain date)
        date_match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', response.url)
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

        # Method 2: Try main media container
        if not images:
            images = response.css('div.media__image img::attr(src)').getall()

        # Method 3: Try figure elements
        if not images:
            images = response.css('figure img::attr(src)').getall()

        # Method 4: Try picture elements
        if not images:
            images = response.css('picture img::attr(src)').getall()

        # Method 5: Try image container
        if not images:
            images = response.css('div.image__container img::attr(src)').getall()

        # Method 6: Try data-src attribute (lazy loading)
        if not images:
            images = response.css('img[data-src]::attr(data-src)').getall()

        # Method 7: Try og:image meta tag as fallback
        if not images:
            og_image = response.css('meta[property="og:image"]::attr(content)').get()
            if og_image:
                images = [og_image]

        # Filter out small icons, logos, and invalid images
        for img_url in images:
            if img_url and self.is_valid_cover_image(img_url):
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
            # CNN images might not have extensions in URL, check for CNN image domains
            if 'cdn.cnn.com' not in url_lower and 'cnn.com' not in url_lower:
                return False

        return True

    def handle_error(self, failure):
        """Handle request errors"""
        self.logger.error(f"Request failed: {failure.request.url}")
        self.logger.error(f"Error: {failure.value}")
