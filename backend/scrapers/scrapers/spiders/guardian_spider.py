import scrapy
from datetime import datetime
from scrapers.items import NewsItem
import re
import json


class GuardianSpider(scrapy.Spider):
    """Spider for crawling The Guardian news website"""

    name = "guardian"
    allowed_domains = ["theguardian.com"]

    # The Guardian main sections
    start_urls = [
        "https://www.theguardian.com/uk/environment",
        "https://www.theguardian.com/us-news/us-politics",
        "https://www.theguardian.com/science",
        "https://www.theguardian.com/uk/technology",
        "https://www.theguardian.com/uk/business",
        "https://www.theguardian.com/uk/sport",
        "https://www.theguardian.com/uk/culture",
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

        # The Guardian uses various selectors for article links
        article_links = []

        # Method 1: Links in card containers (main article cards)
        article_links += response.css('a.dcr-lv2v9o::attr(href)').getall()

        # Method 2: Links with u-faux-block-link class
        article_links += response.css('a.u-faux-block-link__overlay::attr(href)').getall()

        # Method 3: Links in headline containers
        article_links += response.css('a[data-link-name="article"]::attr(href)').getall()

        # Method 4: Links in fc-item containers (front card items)
        article_links += response.css('div.fc-item a::attr(href)').getall()

        # Method 5: Standard article links
        article_links += response.css('article a::attr(href)').getall()

        # Method 6: Links in container with specific Guardian classes
        article_links += response.css('a.js-headline-text::attr(href)').getall()

        # Method 7: Extract from data attributes
        article_links += response.css('a[data-link-name*="article"]::attr(href)').getall()

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

        # Method 1: Main headline
        title = response.css('h1[itemprop="headline"]::text').get()

        # Method 2: Standard h1
        if not title:
            title = response.css('h1::text').get()

        # Method 3: Meta og:title
        if not title:
            title = response.css('meta[property="og:title"]::attr(content)').get()

        # Method 4: Data component headline
        if not title:
            title = response.css('div[data-gu-name="headline"] h1::text').get()

        if not title:
            self.logger.warning(f"No title found for {response.url}")
            return

        # Extract article content
        content_paragraphs = []

        # Method 1: Main article body paragraphs (get all text including nested elements)
        for p in response.css('div[data-gu-name="body"] p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 2: Article body with itemprop
        for p in response.css('div[itemprop="articleBody"] p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 3: Content with specific Guardian classes
        for p in response.css('div.article-body-commercial-selector p, div.content__article-body p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 4: Paragraph blocks
        for p in response.css('p.dcr-1eu361v'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 5: Generic article paragraphs
        if not content_paragraphs:
            for p in response.css('article p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 6: Try blocks with data-component
        if not content_paragraphs:
            for p in response.css('div[data-component="text-block"] p'):
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
                'Sign up' not in p and
                'Newsletter' not in p):
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
        item['source'] = 'The Guardian'
        item['publish_date'] = publish_date
        item['crawl_date'] = datetime.now()
        item['category'] = response.meta.get('category', 'general')

        yield item

    def extract_category(self, url):
        """Extract category from URL"""
        if '/environment' in url:
            return 'Environment'
        elif '/us-politics' in url or '/politics' in url:
            return 'Politics'
        elif '/science' in url:
            return 'Science'
        elif '/technology' in url or '/tech' in url:
            return 'Technology'
        elif '/business' in url:
            return 'Business'
        elif '/sport' in url:
            return 'Sport'
        elif '/culture' in url:
            return 'Culture'
        else:
            return 'General'

    def is_valid_article_url(self, url):
        """Check if URL is a valid Guardian article"""
        if not url:
            return False

        # Must be Guardian domain or relative URL
        if 'theguardian.com' not in url and not url.startswith('/'):
            return False

        # Guardian article URLs typically contain date pattern: /YYYY/MMM/DD/
        # Example: /2024/jan/15/article-title
        if not re.search(r'/\d{4}/[a-z]{3}/\d{2}/', url):
            return False

        # Exclude non-article pages
        exclude_patterns = [
            '/video/',
            '/gallery/',
            '/live/',
            '/ng-interactive/',
            '/interactive/',
            '/series/',
            '/profile/',
            '/info/',
            '/help/',
            '/about/',
            '/membership/',
            '/subscribe/',
            '/newsletters/',
            '/crosswords/',
            '/games/',
        ]

        for pattern in exclude_patterns:
            if pattern in url.lower():
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
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'datePublished' in item:
                            date_str = item['datePublished']
                            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                continue

        # Method 3: Time element with datetime attribute
        time_element = response.css('time::attr(datetime)').get()
        if time_element:
            try:
                return datetime.fromisoformat(time_element.replace('Z', '+00:00'))
            except:
                pass

        # Method 4: Data attribute on time element
        time_data = response.css('time[data-timestamp]::attr(data-timestamp)').get()
        if time_data:
            try:
                # Guardian sometimes uses Unix timestamp in milliseconds
                timestamp = int(time_data) / 1000
                return datetime.fromtimestamp(timestamp)
            except:
                pass

        # Method 5: Extract from URL (Guardian URLs contain date)
        # Format: /2024/jan/15/
        date_match = re.search(r'/(\d{4})/([a-z]{3})/(\d{2})/', response.url)
        if date_match:
            try:
                year, month_abbr, day = date_match.groups()
                # Convert month abbreviation to number
                months = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month = months.get(month_abbr.lower(), 1)
                return datetime(int(year), month, int(day))
            except:
                pass

        # Default to current date if not found
        return datetime.now()

    def extract_cover_image(self, response):
        """Extract the first image from the article as cover image"""
        # Method 1: Try to get image from article body
        images = response.css('article img::attr(src)').getall()

        # Method 2: Try data-gu-name image blocks
        if not images:
            images = response.css('div[data-gu-name="media"] img::attr(src)').getall()

        # Method 3: Try figure elements
        if not images:
            images = response.css('figure img::attr(src)').getall()

        # Method 4: Try picture elements
        if not images:
            images = response.css('picture img::attr(src)').getall()

        # Method 5: Try main media container
        if not images:
            images = response.css('div.article__img-container img::attr(src)').getall()

        # Method 6: Try immersive main media
        if not images:
            images = response.css('div.immersive-main-media img::attr(src)').getall()

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
            # Guardian images might not have extensions in URL, check for Guardian image domains
            if 'guim.co.uk' not in url_lower and 'theguardian.com' not in url_lower:
                return False

        return True

    def handle_error(self, failure):
        """Handle request errors"""
        self.logger.error(f"Request failed: {failure.request.url}")
        self.logger.error(f"Error: {failure.value}")
