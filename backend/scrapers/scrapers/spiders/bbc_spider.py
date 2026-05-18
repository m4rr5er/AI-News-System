import scrapy
from datetime import datetime
from scrapers.items import NewsItem
import re


class BBCSpider(scrapy.Spider):
    """Spider for crawling BBC News homepage and category pages"""

    name = "bbc"
    allowed_domains = ["bbc.com"]

    # BBC category pages
    start_urls = [
        "https://www.bbc.com/sport",
        "https://www.bbc.com/business",
        "https://www.bbc.com/technology",
        "https://www.bbc.com/health",
        "https://www.bbc.com/culture",
        "https://www.bbc.com/arts",
        "https://www.bbc.com/travel",
    ]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    def parse(self, response):
        """Parse category pages to extract article links"""
        self.logger.info(f"Parsing page: {response.url}")

        # Extract category from URL
        category = self.extract_category(response.url)

        # BBC uses various selectors for article links
        # Method 1: Links with data-testid attribute
        article_links = response.css('a[data-testid="internal-link"]::attr(href)').getall()

        # Method 2: Links within article containers
        article_links += response.css('div[data-testid="edinburgh-card"] a::attr(href)').getall()

        # Method 3: Standard article links in news sections
        article_links += response.css('article a::attr(href)').getall()

        # Method 4: Links in promo containers
        article_links += response.css('div.gs-c-promo a.gs-c-promo-heading::attr(href)').getall()

        # Method 5: All links on the page (broader search)
        article_links += response.css('a::attr(href)').getall()

        # Remove duplicates
        article_links = list(set(article_links))

        self.logger.info(f"Found {len(article_links)} total links on {response.url}")

        # Filter and follow article links
        valid_links = []
        for link in article_links:
            if self.is_valid_article_url(link):
                valid_links.append(link)

        self.logger.info(f"Found {len(valid_links)} valid article links on {response.url}")

        for link in valid_links:
            full_url = response.urljoin(link)
            yield scrapy.Request(
                full_url,
                callback=self.parse_article,
                meta={'category': category}
            )

    def parse_article(self, response):
        """Parse individual article page to extract content"""
        self.logger.info(f"Parsing article: {response.url}")

        # Extract title
        title = response.css('h1::text').get()
        if not title:
            title = response.css('h1 *::text').getall()
            title = ' '.join(title).strip() if title else None

        if not title:
            self.logger.warning(f"No title found for {response.url}")
            return

        # Extract article content
        # BBC uses different structures, try multiple selectors
        content_paragraphs = []

        # Method 1: Main article body (get all text including nested elements)
        for p in response.css('article p'):
            text = ''.join(p.css('::text').getall()).strip()
            if text:
                content_paragraphs.append(text)

        # Method 2: Data component text blocks
        if not content_paragraphs:
            for p in response.css('div[data-component="text-block"] p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Method 3: Standard paragraph blocks
        if not content_paragraphs:
            for p in response.css('div.ssrcss-1q0x1qg-Paragraph p'):
                text = ''.join(p.css('::text').getall()).strip()
                if text:
                    content_paragraphs.append(text)

        # Remove duplicates while preserving order
        seen = set()
        unique_paragraphs = []
        for p in content_paragraphs:
            if p and p not in seen:
                seen.add(p)
                unique_paragraphs.append(p)

        # Join content with newlines to preserve paragraph structure
        content = '\n\n'.join(unique_paragraphs)

        if not content:
            self.logger.warning(f"No content found for {response.url}")
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
        item['source'] = 'BBC News'
        item['publish_date'] = publish_date
        item['crawl_date'] = datetime.now()
        item['category'] = response.meta.get('category', 'general')

        yield item

    def extract_category(self, url):
        """Extract category from URL"""
        if '/sport' in url:
            return 'Sport'
        elif '/business' in url:
            return 'Business'
        elif '/technology' in url:
            return 'Technology'
        elif '/health' in url:
            return 'Health'
        elif '/culture' in url:
            return 'Culture'
        elif '/arts' in url:
            return 'Arts'
        elif '/travel' in url:
            return 'Travel'
        else:
            return 'General'

    def is_valid_article_url(self, url):
        """Check if URL is a valid BBC article"""
        if not url:
            return False

        # Exclude non-article pages first
        exclude_patterns = [
            '/live/',
            '/av/',
            '/video',
            '/topics/',
            '/newsbeat',
            'in_pictures',
            'have_your_say',
            '/scores-fixtures',
            '/tables',
            '/results',
            '/fixtures',
            '/standings',
        ]

        for pattern in exclude_patterns:
            if pattern in url:
                return False

        # Valid article URLs have format:
        # - /category/article/article-id or /category/articles/article-id (sport, culture, arts, travel)
        # - /news/articles/article-id (business, technology, health articles)
        # Accept any URL with /article/ or /articles/ in the path
        if '/article/' in url or '/articles/' in url:
            return True

        return False

    def extract_publish_date(self, response):
        """Extract publish date from article page"""
        # Method 1: JSON-LD structured data
        json_ld = response.css('script[type="application/ld+json"]::text').get()
        if json_ld:
            try:
                import json
                data = json.loads(json_ld)
                if isinstance(data, dict) and 'datePublished' in data:
                    date_str = data['datePublished']
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass

        # Method 2: Meta tags
        date_meta = response.css('meta[property="article:published_time"]::attr(content)').get()
        if date_meta:
            try:
                return datetime.fromisoformat(date_meta.replace('Z', '+00:00'))
            except:
                pass

        # Method 3: Time element
        time_element = response.css('time::attr(datetime)').get()
        if time_element:
            try:
                return datetime.fromisoformat(time_element.replace('Z', '+00:00'))
            except:
                pass

        # Default to current date if not found
        return datetime.now()

    def extract_cover_image(self, response):
        """Extract the first image from the article as cover image"""
        # Method 1: Try to get image from article body
        images = response.css('article img::attr(src)').getall()

        # Method 2: Try data-component image blocks
        if not images:
            images = response.css('div[data-component="image-block"] img::attr(src)').getall()

        # Method 3: Try figure elements
        if not images:
            images = response.css('figure img::attr(src)').getall()

        # Method 4: Try picture elements
        if not images:
            images = response.css('picture img::attr(src)').getall()

        # Method 5: Try any img with srcset (BBC often uses responsive images)
        if not images:
            images = response.css('img[srcset]::attr(src)').getall()

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
        ]

        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern in url_lower:
                return False

        # Must be a valid image format
        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        if not any(ext in url_lower for ext in valid_extensions):
            # BBC images might not have extensions in URL, so check for image path patterns
            if 'ichef.bbci.co.uk' not in url_lower and 'bbc.co.uk' not in url_lower:
                return False

        return True
