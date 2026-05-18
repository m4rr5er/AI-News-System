# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class NewsItem(scrapy.Item):
    """News article item for storing scraped news data"""
    title = scrapy.Field()           # News title
    content = scrapy.Field()         # Full news content
    cover_image = scrapy.Field()     # Cover image URL (first image in article)
    url = scrapy.Field()             # News URL
    source = scrapy.Field()          # Source website (e.g., "BBC News")
    publish_date = scrapy.Field()    # Publication date
    crawl_date = scrapy.Field()      # Crawl timestamp
    category = scrapy.Field()        # News category (optional)
