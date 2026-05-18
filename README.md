# AI News Aggregator

一个基于微信小程序的英语新闻学习平台，集成了新闻爬取、AI处理和英语学习功能。

## 项目简介

本项目是一个完整的英文新闻聚合平台，从多个英文新闻网站爬取新闻，使用GLM-4 AI技术进行智能处理，为英语学习者提供优质的学习体验。

### 核心功能

- 📰 **多源新闻聚合**：BBC News, CNN, The Guardian, China Daily
- 🤖 **AI智能处理**：使用GLM-4生成简单英语内容和学习材料
- 📝 **词汇提取**：自动提取30个重点词汇（含音标、翻译、例句）
- 🔍 **背景百科**：AI联网搜索，提供新闻背景信息
- 💬 **AI对话**：基于新闻内容的智能问答
- 🎙️ **AI播客**：生成双语新闻播报音频
- 📊 **观点分析**：提取不同实体的立场和观点

## 技术栈

### 后端
- **爬虫框架**：Scrapy
- **AI模型**：
  - GLM-4-Air：新闻处理
  - GLM-4-Plus：播客脚本生成
- **TTS**：Inworld TTS API
- **云存储**：腾讯云COS
- **数据库**：
  - Redis：去重和缓存
  - MongoDB：原始数据存储
  - MySQL：处理后数据存储
- **API框架**：Flask（待开发）
- **定时任务**：APScheduler（待开发）

### 前端
- **微信小程序**：原生开发框架（待开发）
- **UI组件**：WeUI / Vant Weapp

## 快速开始

### 前置要求

1. **Python 3.9+**
2. **数据库服务**：
   - Redis 5.0+
   - MongoDB 7.0+
   - MySQL 8.0+
3. **API密钥**：
   - 智谱AI GLM-4：https://open.bigmodel.cn/
   - Inworld TTS：https://www.inworld.ai/
   - 腾讯云COS：https://cloud.tencent.com/product/cos

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd AI_News
```

2. **安装依赖**
```bash
pip install scrapy pymongo pymysql redis python-dotenv zai requests cos-python-sdk-v5
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入以下配置：
# - 数据库配置（MongoDB, MySQL, Redis）
# - GLM-4 API密钥
# - Inworld TTS API密钥
# - 腾讯云COS配置（Secret ID, Secret Key）
```

4. **初始化数据库**
```bash
# MySQL
mysql -u root -p < database/mysql/schema.sql

# MongoDB 和 Redis 会自动创建
```

### 运行流程

#### 1. 运行爬虫
```bash
cd backend/scrapers
scrapy crawl bbc
scrapy crawl cnn
scrapy crawl guardian
scrapy crawl chinadaily
```

#### 2. 处理新闻（GLM-4）
```bash
cd backend/processor
python run_processor.py
```

#### 3. 生成每日播客
```bash
cd backend/tts
python daily_podcast_generator.py
```

### 启动API服务

```bash
cd backend/api
python app.py
```

API将在 `http://localhost:5000` 运行

### 运行小程序

1. 安装微信开发者工具
2. 打开项目目录中的 `miniprogram` 文件夹
3. 配置API服务器地址
4. 编译并预览

## 项目结构

```
AI_News/
├── backend/                    # 后端代码
│   ├── scrapers/              # Scrapy爬虫
│   │   └── scrapers/
│   │       ├── spiders/       # 各网站爬虫
│   │       ├── pipelines.py   # 数据处理管道
│   │       └── settings.py    # 爬虫配置
│   ├── processor/             # 新闻处理模块
│   │   ├── news_processor.py  # GLM-4处理器
│   │   └── run_processor.py   # 批处理脚本
│   ├── tts/                   # TTS播客生成
│   │   └── daily_podcast_generator.py
│   └── summarizer/            # AI测试模块
│       └── test_GLM_summarizer.py
├── database/                   # 数据库脚本
│   └── mysql/
│       └── schema.sql         # MySQL表结构
├── tests/                     # 测试文件
│   ├── crawler/              # 爬虫测试
│   ├── processor/            # 处理器测试
│   └── summarizer/           # AI处理测试
└── miniprogram/              # 微信小程序（待开发）
```

## 新闻分类系统

系统直接使用新闻网站的分类，统一了类别名词：

- **Technology** - 科技
- **Business** - 商业
- **Health** - 健康
- **Entertainment** - 娱乐
- **Sports** - 体育
- **World** - 国际

## GLM-4 处理内容

每篇新闻经过GLM-4处理后生成：

1. **simple_title**: 简单英语标题（适合初学者）
2. **simple_content**: 简单英语全文（A2-B1水平）
3. **en_summary**: 英文摘要（60-80词）
4. **difficulty_score**: 难度评分（1-10）
5. **tags**: 3-5个关键词标签
6. **vocabulary**: 30个重点词汇
   - word: 单词
   - phonetic: 音标
   - translation: 中文翻译
   - explanation: 英文解释
   - example_sentence: 例句
7. **background_info**: 背景百科信息（AI联网搜索）
8. **viewpoint_analysis**: 观点分析（实体立场）
9. **entity_relation**: 实体关系
10. **qa_suggestions**: 3个推荐问题

## 数据库设计

### MongoDB (news_raw)
存储原始爬取的新闻数据：
- title, content, url, source, category
- cover_image, publish_date, crawl_date
- is_processed (标记是否已处理)

### MySQL
处理后的数据分布在多个表：
- **news**: 主表（标题、内容、摘要、难度等）
- **vocabulary**: 词汇表（30个/篇）
- **background_info**: 背景百科信息
- **viewpoint_analysis**: 观点分析
- **entity_relation**: 实体关系
- **podcasts**: AI播客（脚本、音频URL、时长等）
- **podcast_news_mapping**: 播客-新闻映射
- **podcast_vocabulary**: 播客词汇（10个/播客）

## 数据流程

```
新闻网站
    ↓
[Scrapy爬虫] → 4个Spider并行运行
    ↓
[Redis去重] → 检查URL唯一性
    ↓
[MongoDB] → 存储原始数据 (is_processed: false)
    ↓
[GLM-4处理] → 生成学习材料
    ↓
[MySQL] → 存储处理后数据 (多表关联)
    ↓
[标记已处理] → MongoDB (is_processed: true)
    ↓
[每日播客生成]
    ↓
[从MySQL选取5篇新闻] → 按类别选择
    ↓
[GLM-4-Plus] → 生成播客脚本
    ↓
[Inworld TTS] → 生成MP3音频
    ↓
[腾讯云COS] → 上传音频文件
    ↓
[MySQL] → 保存播客数据
    ↓
[API服务] → 提供数据接口（待开发）
    ↓
[微信小程序] → 用户使用（待开发）
```

## 性能优化

- ✅ 并行爬取（多个爬虫同时运行）
- ✅ Redis缓存（URL去重）
- ✅ 批量处理（GLM-4批量调用）
- ✅ 连接池（数据库连接复用）
- ⏳ API缓存（待开发）

## 文档

- [数据库设计说明](数据库设计与开发说明.md)
- [小程序功能说明](小程序功能说明.md)
- [处理器使用说明](backend/processor/README.md)

## 开发进度

### 已完成 ✅

- [x] 数据库设计（MySQL, MongoDB, Redis）
- [x] 爬虫开发（BBC, CNN, Guardian, China Daily）
- [x] Redis去重机制
- [x] MongoDB原始数据存储
- [x] GLM-4 AI处理集成
- [x] MySQL处理后数据存储
- [x] AI播客功能（GLM-4-Plus + Inworld TTS）
- [x] 腾讯云COS音频存储

### 待开发 🚧

- [ ] API服务开发
- [ ] 定时任务调度
- [ ] 微信小程序前端
- [ ] 知识图谱可视化

## 测试

### 测试爬虫
```bash
python tests/crawler/test_bbc.py
python tests/crawler/test_cnn.py
python tests/crawler/test_guardian.py
python tests/crawler/test_chinadaily.py
```

### 测试处理器
```bash
python tests/processor/test_news_processor.py
```

### 测试GLM-4
```bash
python tests/summarizer/test_GLM.py
```

### 测试TTS播客生成
```bash
python tests/tts/test_inworld_tts.py
```

## 部署

### 本地部署

1. 启动所有服务（Redis, MongoDB, MySQL）
2. 运行爬虫获取数据
3. 运行处理器处理新闻
4. 运行播客生成器生成每日播客
5. （待开发）启动API服务
6. （待开发）在微信开发者工具中运行小程序

## 常见问题

### Q: 爬虫没有爬取到数据？
A: 检查网络连接，确认目标网站可访问。某些网站可能有反爬虫机制。

### Q: GLM-4 API调用失败？
A:
- 检查API密钥是否正确配置在 `.env` 文件中
- 确认账户余额充足
- 检查网络连接

### Q: MongoDB连接失败？
A: 确认MongoDB服务已启动，检查连接URI是否正确。

### Q: MySQL保存失败？
A:
- 确认MySQL服务已启动
- 检查数据库和表是否已创建（运行schema.sql）
- 检查用户权限

### Q: 播客生成失败？
A:
- 检查Inworld TTS API密钥是否正确
- 确认腾讯云COS配置正确（Secret ID, Secret Key）
- 检查MySQL中是否有足够的新闻数据（每个类别至少1篇）
- 注意Inworld API有速率限制，如遇429错误会自动重试

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

[MIT License](LICENSE)

## 联系方式

如有问题或建议，请提交Issue。

## 致谢

- [Scrapy](https://scrapy.org/) - 爬虫框架
- [智谱AI GLM-4](https://open.bigmodel.cn/) - AI处理
- [Inworld AI](https://www.inworld.ai/) - TTS语音合成
- [腾讯云COS](https://cloud.tencent.com/product/cos) - 对象存储
- [WeChat Mini Program](https://developers.weixin.qq.com/miniprogram/dev/framework/) - 小程序框架

---

**注意**：本项目仅用于学习和研究目的，请遵守相关网站的robots.txt和使用条款。
