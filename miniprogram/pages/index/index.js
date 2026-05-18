const app = getApp();

Page({
  data: {
    // 视图切换控制
    currentTab: 'home',
    showDetail: false,
    activeDetailTab: 'wiki',
    activeCat: 'All',

    // UI 状态控制
    isPlaying: false,
    showDict: false,
    showChat: false,
    showCategorySheet: false,

    // AI 对话状态
    chatMessages: [],       // [{id, role, content}]
    chatInput: '',
    chatLoading: false,
    chatScrollTarget: '',   // scroll-into-view anchor id
    _chatMsgCounter: 0,

    // 接口数据
    newsList: [],
    podcastList: [],
    categories: [],
    selectedNews: null,
    selectedWord: {
      word: '',
      phoneticUK: '',
      phoneticUS: '',
      audioUrlUK: '',
      audioUrlUS: '',
      translation: '',   // fallback for proper nouns with no definitions
      definitions: [],   // [{partOfSpeech, meanings: [{def}]}]
      examples: [],      // [{en, cn}]
      loading: false
    },

    // 搜索状态
    searchQuery: '',
    isSearching: false,
    searchResults: [],
    searchLoading: false,
    searchPage: 1,
    searchHasMore: false,

    // 分页状态
    newsPage: 1,
    newsPageSize: 10,
    newsHasMore: true,
    newsLoading: false,

    // 播客播放器状态
    showFullPlayer: false,
    miniPlayerVisible: false,
    currentPodcastIndex: 0,
    currentPodcast: {},
    podcastLoading: false,
    isOnScriptPage: false,
    playerScrollLeft: 0,
    podcastProgress: 0,
    podcastCurrentTime: '0:00',
    podcastScriptLines: [],

    // Graph 页面状态
    activeGraphTab: 'network',
    graphNodes: [],
    graphEdges: [],
    trendingEntities: [],
    graphLoading: false,
    trendsData: [],
    trendsLoading: false,
    trendsTotalMentions: 0,
    trendsDelta: 0,
    trendsDeltaAbs: 0,
    trendsInsight: '',
    activeTrendsTopic: '',
    trendsTopics: [],
    selectedEntity: { name: '', type: '', description: '', color: 'blue', icon: 'ph-circle', articleCount: 0, articles: [], articlesLoading: false },
    showEntityDetail: false,

    baseUrl: app.globalData.baseUrl,

    // 用户登录状态
    userInfo: null,
    loginLoading: false,
    showProfileModal: false,

    // 浏览历史
    readingHistory: [],
    historyLoading: false,
  },

  onLoad() {
    this.fetchNews(true);
    this.fetchCategories();
    // 恢复登录状态
    const openid = wx.getStorageSync('openid');
    const userInfo = wx.getStorageSync('userInfo');
    if (openid && userInfo) {
      app.globalData.openid = openid;
      this.setData({ userInfo });
    }
  },

  onHide() {
    // 页面隐藏时停止 canvas 动画，防止后台持续消耗内存
    this._stopGraphAnimation();
  },

  onUnload() {
    this._stopGraphAnimation();
    if (this._audioCtx) {
      this._audioCtx.stop();
      this._audioCtx.destroy();
      this._audioCtx = null;
    }
  },

  // --- API 数据获取与预处理 ---
  _formatHeatIndex(list) {
    if (!list || list.length === 0) return [];
    return list.map(item => {
      const hot = Number(item.hot_score) || 0;
      item.heat_index = Math.round(hot * 1000);
      return item;
    });
  },

  _formatNewsList(list) {
    const categoryColors = {
      'technology':    'color: #2563eb; background: #eff6ff;',
      'business':      'color: #0f766e; background: #f0fdfa;',
      'sport':         'color: #ea580c; background: #fff7ed;',
      'health':        'color: #e11d48; background: #fff1f2;',
      'politics':      'color: #4f46e5; background: #eef2ff;',
      'science':       'color: #7c3aed; background: #f5f3ff;',
      'culture':       'color: #c026d3; background: #fdf4ff;',
      'environment':   'color: #059669; background: #ecfdf5;',
      'entertainment': 'color: #db2777; background: #fdf2f8;',
      'travel':        'color: #0891b2; background: #ecfeff;',
      'arts':          'color: #65a30d; background: #f7fee7;',
    };
    const formatted = list.map(item => {
      const key = (item.category || '').toLowerCase();
      item.catStyle = categoryColors[key] || 'color: #4b5563; background: #f3f4f6;';
      item.formatted_time = this.formatTimeAgo(item.publish_date);
      const score = item.difficulty_score;
      if (!score) {
        item.difficultyStyle = 'background: rgba(0,0,0,0.6); color: white;';
      } else if (score <= 4) {
        item.difficultyStyle = 'background: rgba(22,163,74,0.75); color: white;';
      } else if (score <= 6) {
        item.difficultyStyle = 'background: rgba(234,179,8,0.85); color: white;';
      } else if (score <= 8) {
        item.difficultyStyle = 'background: rgba(234,88,12,0.75); color: white;';
      } else {
        item.difficultyStyle = 'background: rgba(220,38,38,0.75); color: white;';
      }
      return item;
    });
    return this._formatHeatIndex(formatted);
  },

  fetchNews(reset) {
    if (this.data.newsLoading) return;
    if (!reset && !this.data.newsHasMore) return;

    const page = reset ? 1 : this.data.newsPage;
    const cat = this.data.activeCat;
    const params = { page, page_size: this.data.newsPageSize };
    if (cat !== 'All') params.category = cat;

    this.setData({ newsLoading: true });

    wx.request({
      url: `${this.data.baseUrl}/api/news/list`,
      data: params,
      success: (res) => {
        if (res.data && res.data.success) {
          const formatted = this._formatNewsList(res.data.data.list || []);
          const total = (res.data.data.pagination && res.data.data.pagination.total) || 0;
          const newList = this._formatHeatIndex(reset ? formatted : this.data.newsList.concat(formatted));
          const hasMore = newList.length < total;
          this.setData({
            newsList: newList,
            newsPage: page + 1,
            newsHasMore: hasMore,
            newsLoading: false,
          });
        } else {
          this.setData({ newsLoading: false });
        }
      },
      fail: (err) => {
        console.error("请求新闻列表失败", err);
        this.setData({ newsLoading: false });
      }
    });
  },

  onNewsScrollToLower() {
    this.fetchNews(false);
  },

  // 计算距离现在的相对时间 (兼容 iOS 和带 T 的 ISO 时间格式)
  formatTimeAgo(dateString) {
    if (!dateString) return 'just now';
    
    // 兼容处理：替换掉 T 和 - ，防止苹果设备解析为 NaN
    const safeDateStr = dateString.replace('T', ' ').replace(/-/g, '/'); 
    const publishDate = new Date(safeDateStr);
    
    if (isNaN(publishDate.getTime())) return dateString; // 如果解析失败，原样返回

    const now = new Date();
    const diffMs = now - publishDate;
    if (diffMs < 0) return 'just now';

    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffDay > 0) return `${diffDay}d ago`;
    if (diffHour > 0) return `${diffHour}h ago`;
    if (diffMin > 0) return `${diffMin}m ago`;
    return 'just now';
  },

  fetchCategories() {
    wx.request({
      url: `${this.data.baseUrl}/api/news/categories`,
      success: (res) => {
        if (res.data && res.data.success) {
          this.setData({ categories: res.data.data });
        }
      }
    });
  },

  fetchNewsDetail(newsId) {
    wx.request({
      url: `${this.data.baseUrl}/api/news/${newsId}`,
      success: (res) => {
        if (res.data && res.data.success) {
          const enriched = this._formatNewsList([res.data.data])[0];
          enriched.contentParagraphs = this._parseContentToParagraphs(enriched.content || '');
          enriched.titleTokens = this._tokenizeLine(enriched.simple_title || enriched.title || '');
          enriched.summaryTokens = this._tokenizeLine(enriched.en_summary || '');
          this.setData({
            selectedNews: enriched,
            showDetail: true,
            // Reset chat when switching articles
            chatMessages: [],
            chatInput: '',
            chatLoading: false,
            chatScrollTarget: '',
            _chatMsgCounter: 0
          });
        }
      }
    });
  },

  // 将无换行的长文本按句子分段，再拆成单词对象数组
  _parseContentToParagraphs(content) {
    if (!content) return [];
    // 按句号/问号/感叹号分句，每3句合为一段
    const sentenceRegex = /[^.!?]+[.!?]+/g;
    const sentences = content.match(sentenceRegex) || [content];
    const paragraphs = [];
    const chunkSize = 3;
    for (let i = 0; i < sentences.length; i += chunkSize) {
      const chunk = sentences.slice(i, i + chunkSize).join(' ').trim();
      if (!chunk) continue;
      paragraphs.push({ id: i, words: this._tokenize(chunk, i) });
    }
    return paragraphs;
  },

  // 将单行文本（标题/摘要）拆成 token 数组
  _tokenizeLine(text) {
    if (!text) return [];
    return this._tokenize(text, 0);
  },

  // 通用 tokenizer：将文本拆成单词+非单词 token
  _tokenize(text, idPrefix) {
    const tokens = text.match(/[a-zA-Z''-]+|[^a-zA-Z''-]+/g) || [];
    return tokens.map((token, idx) => ({
      id: idPrefix + '_' + idx,
      text: token,
      isWord: /[a-zA-Z]/.test(token)
    }));
  },

  // 点击单词：先展示单词，再调词典 API
  tapWord(e) {
    const { text, isWord } = e.currentTarget.dataset;
    if (!isWord || !text) return;
    const word = text.replace(/[^a-zA-Z'-]/g, '').toLowerCase();
    if (!word) return;
    this.setData({
      showDict: true,
      selectedWord: { word, phoneticUK: '', phoneticUS: '', audioUrlUK: '', audioUrlUS: '', translation: '', definitions: [], examples: [], loading: true }
    });
    this._lookupWord(word);
  },

  _lookupWord(word) {
    console.log('[dict] lookup url=', `${this.data.baseUrl}/api/dict/lookup`, 'word=', word);
    wx.request({
      url: `${this.data.baseUrl}/api/dict/lookup`,
      data: { word },
      success: (res) => {
        console.log('[dict] response statusCode=', res.statusCode, 'data keys=', res.data ? Object.keys(res.data) : 'null');
        const d = res.data;
        if (!d) {
          this.setData({ 'selectedWord.loading': false });
          return;
        }

        let phoneticUK = '', phoneticUS = '';
        let audioUrlUK = '', audioUrlUS = '';
        const ec = d.ec;
        console.log('[dict] ec=', JSON.stringify(ec && ec.word && ec.word[0] ? {ukphone: ec.word[0].ukphone, trs_count: ec.word[0].trs ? ec.word[0].trs.length : 0, first_tr: ec.word[0].trs && ec.word[0].trs[0]} : ec));
        if (ec && ec.word && ec.word[0]) {
          const w = ec.word[0];
          phoneticUK = w.ukphone || '';
          phoneticUS = w.usphone || '';
          // ukspeech/usspeech 格式如 "noma&type=1"，需要提取音频key并正确传递
          if (w.ukspeech) {
            const audioKey = w.ukspeech.split('&')[0]; // 提取 & 前面的部分
            audioUrlUK = `${this.data.baseUrl}/api/dict/audio?key=${audioKey}&type=1`;
          }
          if (w.usspeech) {
            const audioKey = w.usspeech.split('&')[0];
            audioUrlUS = `${this.data.baseUrl}/api/dict/audio?key=${audioKey}&type=2`;
          }
        }

        // 例句来自 blng_sents_part（双语例句库）
        const exampleSentences = [];
        const blng = d.blng_sents_part;
        if (blng && blng['sentence-pair']) {
          blng['sentence-pair'].forEach(pair => {
            if (pair.sentence && pair['sentence-translation']) {
              exampleSentences.push({
                en: pair.sentence.replace(/<\/?b>/g, ''),
                cn: pair['sentence-translation']
              });
            }
          });
        }

        const examples = [];
        const seenExampleKeys = new Set();
        exampleSentences.forEach(ex => {
          const key = `${ex.en}__${ex.cn}`;
          if (seenExampleKeys.has(key)) return;
          seenExampleKeys.add(key);
          examples.push(ex);
        });

        // 词性 + 中文释义
        const definitions = [];
        if (ec && ec.word && ec.word[0] && ec.word[0].trs) {
          // 有道 trs 里每条 def 字符串形如 "n. 家，住宅；..." 或直接是释义
          // 按词性前缀分组，提取出干净的中文释义
          const posMap = {};

          ec.word[0].trs.forEach(tr => {
            const iArr = tr.tr && tr.tr[0] && tr.tr[0].l && tr.tr[0].l.i;
            const raw = iArr ? (Array.isArray(iArr) ? iArr[0] : iArr) : '';
            if (!raw) return;

            // 从字符串开头提取词性标记，如 "n." "v." "adj." "adv." "prep." "conj." "pron." "int."
            const posMatch = raw.match(/^([a-z]+\.\s*(?:\([^)]+\)\s*)?)/);
            let pos, def;
            if (posMatch) {
              pos = posMatch[1].trim();
              def = raw.slice(posMatch[1].length).trim();
            } else if (tr.pos) {
              pos = tr.pos;
              def = raw;
            } else {
              pos = '释义';
              def = raw;
            }

            if (!def) return;
            if (!posMap[pos]) posMap[pos] = [];
            if (posMap[pos].length >= 3) return;
            posMap[pos].push({ def });
          });

          Object.keys(posMap).forEach(pos => {
            definitions.push({ partOfSpeech: pos, meanings: posMap[pos] });
          });
        }

        // 专有名词兜底翻译
        let translation = '';
        if (!definitions.length && d.fanyi && d.fanyi.tran) {
          translation = d.fanyi.tran;
        }

        console.log('[dict] definitions=', JSON.stringify(definitions), 'translation=', translation, 'phoneticUK=', phoneticUK);
        this.setData({
          'selectedWord.phoneticUK': phoneticUK,
          'selectedWord.phoneticUS': phoneticUS,
          'selectedWord.audioUrlUK': audioUrlUK,
          'selectedWord.audioUrlUS': audioUrlUS,
          'selectedWord.definitions': definitions,
          'selectedWord.examples': examples.slice(0, 3),
          'selectedWord.translation': translation,
          'selectedWord.loading': false
        });

        // 如果有道完全没有结果（专有名词），再用 fanyi 接口补充
        if (!translation && !definitions.length && !phoneticUK && !phoneticUS) {
          this._fetchFanyiTranslation(word);
        }
      },
      fail: (err) => {
        console.error('[dict] request FAILED:', JSON.stringify(err));
        this.setData({ 'selectedWord.loading': false });
        this._fetchFanyiTranslation(word);
      }
    });
  },

  // 兜底：有道翻译接口，处理专有名词/查不到的词
  _fetchFanyiTranslation(word) {
    wx.request({
      url: `${this.data.baseUrl}/api/dict/fanyi`,
      data: { word },
      success: (res) => {
        const result = res.data && res.data.translateResult;
        if (result && result[0] && result[0][0]) {
          const tran = result[0][0].tgt || '';
          if (tran && tran !== word) {
            this.setData({ 'selectedWord.translation': tran });
          }
        }
      }
    });
  },

  // 播放单词发音，type: 'uk' | 'us'
  playWordAudio(e) {
    const type = (e && e.currentTarget && e.currentTarget.dataset.type) || 'uk';
    const sw = this.data.selectedWord;
    const url = type === 'us' ? sw.audioUrlUS : sw.audioUrlUK;
    if (!url) {
      wx.showToast({ title: '暂无发音', icon: 'none', duration: 1200 });
      return;
    }
    const audio = wx.createInnerAudioContext();
    audio.src = url;
    audio.play();
  },

  // --- 视图与导航交互 ---
  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    // 离开 graph tab 时停止动画
    if (this.data.currentTab === 'graph' && tab !== 'graph') {
      this._stopGraphAnimation();
    }
    this.setData({ currentTab: tab });
    if (tab === 'podcast' && this.data.podcastList.length === 0) {
      this.fetchPodcasts();
    }
    if (tab === 'graph') {
      if (this.data.trendingEntities.length === 0) {
        this.fetchTrendingEntities();
      }
      // canvas 需要等 DOM 渲染完成后再初始化
      setTimeout(() => { this._initGraphCanvas(); }, 100);
    }
    if (tab === 'me' && this.data.userInfo) {
      this.fetchReadingHistory();
    }
  },

  fetchPodcasts() {
    this.setData({ podcastLoading: true });
    wx.request({
      url: `${this.data.baseUrl}/api/podcast/list`,
      success: (res) => {
        if (res.data && res.data.success) {
          const list = (res.data.data.list || []).map(item => {
            item.duration_str = this._formatDuration(item.duration);
            item.duration_label = this._formatDurationLabel(item.duration);
            item.formatted_date = this._formatPodcastDate(item.created_at);
            return item;
          });
          this.setData({ podcastList: list, podcastLoading: false });
        } else {
          this.setData({ podcastLoading: false });
        }
      },
      fail: () => { this.setData({ podcastLoading: false }); }
    });
  },

  // 格式化秒数为 m:ss
  _formatDuration(seconds) {
    if (!seconds) return '0:00';
    const s = Math.floor(seconds);
    return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;
  },

  _formatDurationLabel(seconds) {
    if (!seconds) return '0 sec';
    const s = Math.floor(seconds);
    const m = Math.floor(s / 60);
    const sec = s % 60;
    if (m === 0) return `${sec} sec`;
    if (sec === 0) return `${m} min`;
    return `${m} min ${sec} sec`;
  },

  // 格式化播客日期
  _formatPodcastDate(dateStr) {
    if (!dateStr) return '';
    const safe = dateStr.replace('T', ' ').replace(/-/g, '/');
    const d = new Date(safe);
    if (isNaN(d.getTime())) return dateStr;
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
  },

  // 打开全屏播放器
  openPodcastPlayer(e) {
    const index = e && e.currentTarget ? (e.currentTarget.dataset.index || 0) : (this.data.currentPodcastIndex || 0);
    const list = this.data.podcastList;
    if (!list || list.length === 0) return;

    // 切换播客时销毁旧的音频上下文
    if (this._audioCtx && this.data.currentPodcastIndex !== index) {
      this._audioCtx.stop();
      this._audioCtx.destroy();
      this._audioCtx = null;
      this.setData({ isPlaying: false, podcastProgress: 0, podcastCurrentTime: '0:00' });
    }

    const podcast = list[index] || list[0];
    this.setData({
      showFullPlayer: true,
      currentPodcastIndex: index,
      currentPodcast: podcast,
      isOnScriptPage: false,
      playerScrollLeft: 0,
      podcastScriptLines: this._parseScript(podcast.script || ''),
    });

    // 如果还没有加载详情（vocabulary + news），则拉取
    if (!podcast._detailLoaded) {
      this._fetchPodcastDetail(podcast.id, index);
    }
  },

  // 关闭全屏播放器，显示 mini player
  closePodcastPlayer() {
    this.setData({
      showFullPlayer: false,
      miniPlayerVisible: true,
    });
  },

  // 拉取播客详情（vocabulary + source news）
  _fetchPodcastDetail(podcastId, index) {
    wx.request({
      url: `${this.data.baseUrl}/api/podcast/${podcastId}`,
      success: (res) => {
        if (res.data && res.data.success) {
          const detail = res.data.data;
          const categoryColors = {
            'technology': 'color: #2563eb; background: rgba(37,99,235,0.2);',
            'business':   'color: #0f766e; background: rgba(15,118,110,0.2);',
            'sport':      'color: #ea580c; background: rgba(234,88,12,0.2);',
            'health':     'color: #e11d48; background: rgba(225,29,72,0.2);',
            'politics':   'color: #4f46e5; background: rgba(79,70,229,0.2);',
            'science':    'color: #7c3aed; background: rgba(124,58,237,0.2);',
            'culture':    'color: #c026d3; background: rgba(192,38,211,0.2);',
            'environment':'color: #059669; background: rgba(5,150,105,0.2);',
            'entertainment':'color: #db2777; background: rgba(219,39,119,0.2);',
            'travel':     'color: #0891b2; background: rgba(8,145,178,0.2);',
            'arts':       'color: #65a30d; background: rgba(101,163,13,0.2);',
          };
          if (detail.news) {
            detail.news = detail.news.map(n => {
              const key = (n.category || '').toLowerCase();
              n.catStyle = categoryColors[key] || 'color: #9ca3af; background: rgba(156,163,175,0.2);';
              return n;
            });
          }
          detail._detailLoaded = true;
          detail.duration_str = this._formatDuration(detail.duration);
          detail.duration_label = this._formatDurationLabel(detail.duration);
          detail.formatted_date = this._formatPodcastDate(detail.created_at);

          // Update list and current podcast
          const list = this.data.podcastList;
          list[index] = detail;
          const updates = { podcastList: list };
          if (this.data.currentPodcastIndex === index) {
            updates.currentPodcast = detail;
            updates.podcastScriptLines = this._parseScript(detail.script || '');
          }
          this.setData(updates);
        }
      }
    });
  },

  // 解析播客脚本为 [{speaker, text}] 数组
  // 支持格式: "Host_A: text\nHost_B: text" (TTS格式) 或 "Brian: text" 或 JSON 数组
  _parseScript(script) {
    if (!script) return [];
    // 尝试 JSON 解析
    try {
      const parsed = JSON.parse(script);
      if (Array.isArray(parsed)) return parsed;
    } catch (e) { /* not JSON */ }

    // 按行解析，支持 Host_A/Host_B 和 Brian/Jessica 两种格式
    const lines = script.split('\n').filter(l => l.trim());
    const result = [];
    for (const line of lines) {
      const colonIdx = line.indexOf(':');
      if (colonIdx > 0 && colonIdx < 20) {
        let speaker = line.slice(0, colonIdx).trim();
        const text = line.slice(colonIdx + 1).trim();
        // 将 Host_A/Host_B 映射为真实名字
        if (speaker === 'Host_A') speaker = 'Brian';
        else if (speaker === 'Host_B') speaker = 'Jessica';
        if (text) result.push({ speaker, text });
      } else if (line.trim()) {
        result.push({ speaker: '', text: line.trim() });
      }
    }
    return result;
  },

  // 切换播放器页面（封面 ↔ 脚本）
  togglePlayerPage() {
    const going = !this.data.isOnScriptPage;
    this.setData({
      isOnScriptPage: going,
      playerScrollLeft: going ? 750 : 0,  // 750 = approximate page width in px
    });
  },

  // 监听横滑，同步 dot 指示器
  onPlayerScroll(e) {
    const scrollLeft = e.detail.scrollLeft;
    // 获取容器宽度（rpx 转 px 约为 screenWidth/750）
    const pageWidth = wx.getWindowInfo().windowWidth;
    const onScript = scrollLeft > pageWidth / 2;
    if (onScript !== this.data.isOnScriptPage) {
      this.setData({ isOnScriptPage: onScript });
    }
  },

  // 滑动结束后吸附到最近的页面
  onPlayerScrollEnd(e) {
    const scrollLeft = e.detail.scrollLeft;
    const pageWidth = wx.getWindowInfo().windowWidth;
    const targetPage = scrollLeft > pageWidth / 2 ? 1 : 0;
    const targetScrollLeft = targetPage * pageWidth;
    const isOnScript = targetPage === 1;
    this.setData({
      playerScrollLeft: targetScrollLeft,
      isOnScriptPage: isOnScript,
    });
  },

  // 播放/暂停
  togglePlay() {
    const playing = !this.data.isPlaying;
    const podcast = this.data.currentPodcast;

    console.log('[togglePlay] playing=', playing, 'audio_url=', podcast && podcast.audio_url);

    if (!podcast || !podcast.audio_url) {
      wx.showToast({ title: '暂无音频', icon: 'none', duration: 1500 });
      return;
    }

    this.setData({ isPlaying: playing });

    if (!this._audioCtx) {
      console.log('[togglePlay] creating InnerAudioContext, src=', podcast.audio_url);
      this._audioCtx = wx.createInnerAudioContext();
      this._audioCtx.src = podcast.audio_url;
      const knownDuration = podcast.duration || 0;
      this._audioCtx.onCanplay(() => {
        console.log('[audio] canplay, duration=', this._audioCtx.duration);
      });
      this._audioCtx.onPlay(() => {
        console.log('[audio] onPlay fired');
      });
      this._audioCtx.onTimeUpdate(() => {
        const cur = this._audioCtx.currentTime || 0;
        const ctxDur = this._audioCtx.duration;
        const dur = (ctxDur && ctxDur > 10) ? ctxDur : knownDuration;
        if (!dur || dur <= 0) return;
        const progress = Math.min((cur / dur) * 100, 100);
        this.setData({
          podcastProgress: progress,
          podcastCurrentTime: this._formatDuration(cur),
        });
      });
      this._audioCtx.onEnded(() => {
        this.setData({ isPlaying: false, podcastProgress: 100 });
      });
      this._audioCtx.onError((err) => {
        console.error('[audio] ERROR:', JSON.stringify(err));
        this.setData({ isPlaying: false });
        wx.showToast({ title: '音频错误:' + (err.errMsg || err.errCode || ''), icon: 'none', duration: 3000 });
      });
    }

    console.log('[togglePlay] calling', playing ? 'play()' : 'pause()');
    playing ? this._audioCtx.play() : this._audioCtx.pause();
  },

  // 快退 15 秒
  rewindPodcast() {
    if (this._audioCtx) {
      this._audioCtx.seek(Math.max(0, (this._audioCtx.currentTime || 0) - 15));
    }
  },

  // 快进 15 秒
  forwardPodcast() {
    if (this._audioCtx) {
      this._audioCtx.seek((this._audioCtx.currentTime || 0) + 15);
    }
  },

  // 点击进度条跳转
  seekPodcast(e) {
    const rect = e.currentTarget.getBoundingClientRect
      ? e.currentTarget.getBoundingClientRect()
      : { left: 0, width: 1 };
    const progress = Math.max(0, Math.min(100, ((e.detail.x - (rect.left || 0)) / (rect.width || 1)) * 100));
    this.setData({ podcastProgress: progress });
    if (this._audioCtx && this._audioCtx.duration) {
      this._audioCtx.seek((progress / 100) * this._audioCtx.duration);
    }
  },

  // 从播客脚本页跳转到新闻详情
  jumpToNewsFromPodcast(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({ showFullPlayer: false });
    setTimeout(() => { this.fetchNewsDetail(id); }, 300);
  },

  goToDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (id) {
      this.fetchNewsDetail(id);
      // 登录后自动记录浏览历史
      const openid = app.globalData.openid;
      if (openid) {
        wx.request({
          url: `${this.data.baseUrl}/api/auth/history`,
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          data: { user_id: openid, news_id: id }
        });
      }
    }
  },

  goBack() {
    this.setData({ showDetail: false });
  },

  _normalizeSourceUrl(url) {
    let link = String(url || '').trim();
    if (!link) return '';
    if (link.startsWith('//')) link = `https:${link}`;
    if (/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(link)) return link;
    if (/^[\w.-]+\.[a-z]{2,}([/?#].*)?$/i.test(link)) return `https://${link}`;
    return '';
  },

  openSourceUrl() {
    const url = this._normalizeSourceUrl(this.data.selectedNews && this.data.selectedNews.original_url);
    if (!url) return;
    wx.navigateTo({
      url: `/pages/webview/webview?url=${encodeURIComponent(url)}`,
      fail: () => {
        wx.setClipboardData({
          data: url,
          success: () => wx.showToast({ title: 'Link copied', icon: 'none', duration: 1500 })
        });
      }
    });
  },

  copySourceUrl() {
    const url = this._normalizeSourceUrl(this.data.selectedNews && this.data.selectedNews.original_url);
    if (!url) return;
    wx.setClipboardData({
      data: url,
      success: () => wx.showToast({ title: 'Link copied', icon: 'success', duration: 1500 })
    });
  },

  switchDetailTab(e) {
    this.setData({ activeDetailTab: e.currentTarget.dataset.tab });
  },

  // --- 功能交互 ---
  openDict(e) {
    const { word, phonetic, translation, explanation } = e.currentTarget.dataset;
    this.setData({
      showDict: true,
      selectedWord: {
        word: word || 'disaster',
        phoneticUK: phonetic || '/dɪˈzɑːstə/',
        phoneticUS: '',
        audioUrlUK: '',
        audioUrlUS: '',
        translation: translation || '灾难',
        explanation: explanation || 'A sudden event that causes great damage or loss of life.',
        definitions: [],
        examples: [],
        loading: false
      }
    });
  },

  closeDict() {
    this.setData({ showDict: false });
  },

  toggleChat() {
    this.setData({ showChat: !this.data.showChat });
  },

  closeChat() {
    this.setData({ showChat: false });
  },

  clearChat() {
    this.setData({ chatMessages: [], chatInput: '', chatScrollTarget: '', _chatMsgCounter: 0 });
  },

  onChatInput(e) {
    this.setData({ chatInput: e.detail.value });
  },

  sendSuggestion(e) {
    const text = e.currentTarget.dataset.text;
    if (text) this._doSendChat(text);
  },

  sendChat() {
    const text = (this.data.chatInput || '').trim();
    if (!text || this.data.chatLoading) return;
    this._doSendChat(text);
  },

  _doSendChat(text) {
    const newsId = this.data.selectedNews && this.data.selectedNews.id;
    if (!newsId) return;

    // Append user message
    let counter = this.data._chatMsgCounter + 1;
    const userMsg = { id: counter, role: 'user', content: text };
    const messages = this.data.chatMessages.concat(userMsg);
    counter++;

    this.setData({
      chatMessages: messages,
      chatInput: '',
      chatLoading: true,
      _chatMsgCounter: counter,
      chatScrollTarget: 'chat-bottom'
    });

    // Build history for backend (exclude the message we just added)
    const history = messages.slice(0, -1).map(m => ({ role: m.role, content: m.content }));

    wx.request({
      url: `${this.data.baseUrl}/api/chat/question`,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: {
        news_id: newsId,
        question: text,
        history: history.length > 0 ? history : undefined
      },
      success: (res) => {
        if (res.data && res.data.success) {
          const aiMsg = { id: counter, role: 'assistant', content: res.data.data.answer };
          this.setData({
            chatMessages: this.data.chatMessages.concat(aiMsg),
            chatLoading: false,
            _chatMsgCounter: counter + 1,
            chatScrollTarget: 'chat-bottom'
          });
        } else {
          this._chatError('请求失败，请重试');
        }
      },
      fail: () => {
        this._chatError('网络错误，请检查连接');
      }
    });
  },

  _chatError(msg) {
    const counter = this.data._chatMsgCounter + 1;
    const errMsg = { id: counter, role: 'assistant', content: `⚠️ ${msg}` };
    this.setData({
      chatMessages: this.data.chatMessages.concat(errMsg),
      chatLoading: false,
      _chatMsgCounter: counter + 1,
      chatScrollTarget: 'chat-bottom'
    });
  },

  // --- 搜索功能 ---
  onSearchInput(e) {
    const query = e.detail.value;
    this.setData({ searchQuery: query });
    if (!query.trim()) {
      this.setData({ isSearching: false, searchResults: [] });
      return;
    }
    // 防抖：300ms 后触发搜索
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => {
      this._doSearch(query.trim(), true);
    }, 300);
  },

  onSearchConfirm(e) {
    const query = (e.detail.value || '').trim();
    if (!query) return;
    clearTimeout(this._searchTimer);
    this._doSearch(query, true);
  },

  clearSearch() {
    clearTimeout(this._searchTimer);
    this.setData({ searchQuery: '', isSearching: false, searchResults: [], searchPage: 1, searchHasMore: false });
  },

  _doSearch(query, reset) {
    if (this.data.searchLoading) return;
    const page = reset ? 1 : this.data.searchPage;
    this.setData({ searchLoading: true, isSearching: true });

    wx.request({
      url: `${this.data.baseUrl}/api/news/search`,
      data: { q: query, page, page_size: 10 },
      success: (res) => {
        if (res.data && res.data.success) {
          const formatted = this._formatNewsList(res.data.data.list || []);
          const total = (res.data.data.pagination && res.data.data.pagination.total) || 0;
          const newList = this._formatHeatIndex(reset ? formatted : this.data.searchResults.concat(formatted));
          this.setData({
            searchResults: newList,
            searchPage: page + 1,
            searchHasMore: newList.length < total,
            searchLoading: false,
          });
        } else {
          this.setData({ searchLoading: false });
        }
      },
      fail: () => {
        this.setData({ searchLoading: false });
      }
    });
  },

  onSearchScrollToLower() {
    if (this.data.searchHasMore && this.data.searchQuery.trim()) {
      this._doSearch(this.data.searchQuery.trim(), false);
    }
  },

  toggleCategorySheet() {
    this.setData({ showCategorySheet: !this.data.showCategorySheet });
  },

  switchCat(e) {
    const cat = e.currentTarget.dataset.cat;
    if (cat === this.data.activeCat) return;
    this.setData({ activeCat: cat, newsList: [], newsPage: 1, newsHasMore: true });
    this.fetchNews(true);
  },

  switchCatFromSheet(e) {
    const cat = e.currentTarget.dataset.cat;
    this.setData({ activeCat: cat, showCategorySheet: false, newsList: [], newsPage: 1, newsHasMore: true });
    this.fetchNews(true);
  },

  // --- Graph Canvas 绘制 ---

  // 初始化 canvas 图谱（在切换到 graph tab 后调用）
  _initGraphCanvas() {
    // 已初始化过也重新套用 demo 布局，避免复用旧节点位置。
    if (this._graphCanvas && this._graphCtx) {
      this._initMockGraphData();
      this._startGraphAnimation();
      return;
    }
    const query = wx.createSelectorQuery();
    query.select('#graphCanvas')
      .fields({ node: true, size: true, rect: true })
      .exec((res) => {
        if (!res || !res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const width = res[0].width;
        const height = res[0].height;
        if (!width || !height) {
          setTimeout(() => { this._initGraphCanvas(); }, 80);
          return;
        }
        const dpr = wx.getWindowInfo().pixelRatio;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        this._graphCanvas = canvas;
        this._graphCtx = ctx;
        this._graphW = width;
        this._graphH = height;
        this._graphDpr = dpr;
        this._graphCanvasLeft = res[0].left || 0;
        this._graphCanvasTop = res[0].top || 0;
        this._graphDragNode = null;
        this._graphAnimFrame = null;

        this._initMockGraphData();

        // 脉冲动画状态
        this._graphPulse = 0;
        this._graphFlowOffset = 0;
        this._startGraphAnimation();
      });
  },

  _getDefaultGraphTopic() {
    const firstTrending = this.data.trendingEntities && this.data.trendingEntities[0];
    return (firstTrending && firstTrending.entity_name) || this.data.activeTrendsTopic || 'AI';
  },

  _getGraphTopics(preferredTopic) {
    const topics = [];
    if (preferredTopic) topics.push(preferredTopic);
    (this.data.trendingEntities || []).slice(0, 6).forEach(entity => {
      if (entity.entity_name) topics.push(entity.entity_name);
    });
    if (this.data.activeTrendsTopic) topics.push(this.data.activeTrendsTopic);
    topics.push('AI', 'Technology', 'Business');
    return [...new Set(topics)].slice(0, 6);
  },

  _getGraphTypeStyle(typeRaw) {
    const type = (typeRaw || '').toLowerCase();
    if (type === 'person') {
      return { color: '#7c3aed', stroke: '#a78bfa' };
    }
    if (type === 'concept') {
      return { color: '#059669', stroke: '#34d399' };
    }
    if (type === 'location') {
      return { color: '#ea580c', stroke: '#fb923c' };
    }
    return { color: '#2563eb', stroke: '#60a5fa' };
  },

  _shortGraphLabel(label) {
    const text = String(label || '').trim();
    if (text.length <= 10) return text;
    const words = text.split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
      return words.map(w => w[0]).join('').slice(0, 8);
    }
    return `${text.slice(0, 8)}…`;
  },

  _shortGraphRelation(label) {
    const text = String(label || 'related_to').trim();
    return text.length <= 14 ? text : `${text.slice(0, 12)}…`;
  },

  _getGraphTouchPoint(touch) {
    let x = touch.x;
    let y = touch.y;
    if (x > this._graphW + 20 && this._graphCanvasLeft) {
      x -= this._graphCanvasLeft;
    }
    if (y > this._graphH + 20 && this._graphCanvasTop) {
      y -= this._graphCanvasTop;
    }
    return { x, y };
  },

  _initMockGraphData() {
    if (!this._graphW || !this._graphH) return;
    const W = this._graphW;
    const H = this._graphH;
    const ART_W = 400;
    const ART_H = 300;
    const scale = Math.min(W / ART_W, H / ART_H);
    const offsetX = (W - ART_W * scale) / 2;
    const offsetY = (H - ART_H * scale) / 2;
    const point = (x, y) => ({ x: offsetX + x * scale, y: offsetY + y * scale });

    const nodes = [
      {
        id: 'OpenAI',
        label: 'OpenAI',
        type: 'organization',
        description: 'An AI safety company founded in 2015, known for developing GPT series models and ChatGPT.',
        r: 24,
        ...point(200, 150)
      },
      {
        id: 'GPT-4',
        label: 'GPT-4',
        type: 'concept',
        description: "OpenAI's most advanced large language model, released in March 2023, with multimodal capabilities.",
        r: 18,
        ...point(80, 80)
      },
      {
        id: 'Microsoft',
        label: 'Microsoft',
        type: 'organization',
        description: 'Technology giant that invested $13 billion in OpenAI and integrated its models into Azure and Bing.',
        r: 20,
        ...point(320, 70)
      },
      {
        id: 'Sam Altman',
        label: 'Altman',
        type: 'person',
        description: 'CEO of OpenAI, previously president of Y Combinator. Briefly ousted in Nov 2023 before being reinstated.',
        r: 18,
        ...point(120, 240)
      },
      {
        id: 'xAI',
        label: 'xAI',
        type: 'organization',
        description: 'An artificial intelligence company founded by Elon Musk, aiming to understand the true nature of the universe.',
        r: 18,
        ...point(320, 180)
      },
      {
        id: 'Elon Musk',
        label: 'E. Musk',
        type: 'person',
        description: 'Entrepreneur and business magnate, founder of SpaceX, Tesla, and xAI.',
        r: 18,
        ...point(350, 260)
      },
      {
        id: 'Federal Reserve',
        label: 'Fed Rsrv',
        type: 'organization',
        description: 'The central banking system of the United States, responsible for monetary policy and interest rate decisions.',
        r: 22,
        ...point(70, 180)
      },
      {
        id: 'Jerome Powell',
        label: 'Powell',
        type: 'person',
        description: 'Chair of the Federal Reserve since 2018, appointed by President Trump and reappointed by President Biden.',
        r: 18,
        ...point(50, 260)
      },
      {
        id: 'Interest Rate',
        label: 'Rate Hike',
        type: 'concept',
        description: 'A policy change in interest rates following Federal Reserve decisions.',
        r: 18,
        ...point(160, 280)
      }
    ];

    this._graphNodes = nodes.map((node, index) => {
      const style = this._getGraphTypeStyle(node.type);
      return {
        ...node,
        fullLabel: node.id,
        color: style.color,
        stroke: style.stroke,
        isCenter: index === 0
      };
    });

    this._graphEdges = [
      { from: 'GPT-4', to: 'OpenAI', label: 'created_by', color: '#34d399', textColor: '#a7f3d0', width: 1.5 },
      { from: 'Microsoft', to: 'OpenAI', label: 'invested_in', color: '#60a5fa', textColor: '#bfdbfe', width: 2 },
      { from: 'OpenAI', to: 'Sam Altman', label: 'developed_by', color: '#60a5fa', textColor: '#bfdbfe', width: 1.5 },
      { from: 'xAI', to: 'OpenAI', label: 'competes_with', color: '#f472b6', textColor: '#fbcfe8', width: 1.5 },
      { from: 'Elon Musk', to: 'xAI', label: 'founded', color: '#a78bfa', textColor: '#ddd6fe', width: 1.5 },
      { from: 'Federal Reserve', to: 'Jerome Powell', label: 'chaired_by', color: '#60a5fa', textColor: '#bfdbfe', width: 1.5 },
      { from: 'Jerome Powell', to: 'Interest Rate', label: 'announced', color: '#a78bfa', textColor: '#ddd6fe', width: 1.5 }
    ];

    this._graphNodeById = this._graphNodes.reduce((map, node) => {
      map[node.id] = node;
      return map;
    }, {});
    this.setData({
      graphNodes: this._graphNodes.map(node => ({
        id: node.id,
        label: node.fullLabel,
        type: node.type,
        description: node.description
      })),
      graphEdges: this._graphEdges.map(edge => ({
        source: edge.from,
        target: edge.to,
        relation: edge.label
      }))
    });
    this._drawGraph();
  },

  _syncGraphCanvasData() {
    if (!this._graphW || !this._graphH) return;

    const rawNodes = this.data.graphNodes || [];
    const rawEdges = this.data.graphEdges || [];
    const nodeMap = {};

    rawNodes.forEach(node => {
      const id = node.id || node.label || node.entity_name;
      if (!id) return;
      nodeMap[id] = {
        id,
        label: node.label || id,
        type: node.type || node.entity_type || 'Unknown',
        description: node.description || '',
        articleCount: Number(node.article_count || node.articleCount || 0)
      };
    });

    if (Object.keys(nodeMap).length === 0 || rawEdges.length === 0) {
      this._graphNodes = [];
      this._graphEdges = [];
      this._graphNodeById = {};
      this._drawGraph();
      return;
    }

    const degreeMap = {};
    rawEdges.forEach(edge => {
      const from = edge.source || edge.from;
      const to = edge.target || edge.to;
      if (!from || !to) return;
      degreeMap[from] = (degreeMap[from] || 0) + 1;
      degreeMap[to] = (degreeMap[to] || 0) + 1;
    });

    const topNodes = Object.values(nodeMap)
      .map(node => {
        const degree = degreeMap[node.id] || 0;
        const articleCount = Number(node.articleCount || 0);
        return {
          ...node,
          _id: node.id,
          _degree: degree,
          _articleCount: articleCount,
          _score: degree * 80 + articleCount * 12
        };
      })
      .filter(node => node._degree > 0)
      .sort((a, b) => b._score - a._score)
      .slice(0, 16);

    if (topNodes.length === 0) {
      this._graphNodes = [];
      this._graphEdges = [];
      this._graphNodeById = {};
      this._drawGraph();
      return;
    }

    let allowedIds = new Set(topNodes.map(node => node._id));
    let graphEdges = rawEdges
      .map((edge, index) => {
        const from = edge.source || edge.from;
        const to = edge.target || edge.to;
        if (!allowedIds.has(from) || !allowedIds.has(to)) return null;
        const colorPool = ['#60a5fa', '#34d399', '#a78bfa', '#f472b6', '#fb923c'];
        return {
          from,
          to,
          label: this._shortGraphRelation(edge.relation || edge.label),
          color: colorPool[index % colorPool.length]
        };
      })
      .filter(Boolean)
      .slice(0, 18);

    const edgeNodeIds = new Set();
    graphEdges.forEach(edge => {
      edgeNodeIds.add(edge.from);
      edgeNodeIds.add(edge.to);
    });
    let displayNodes = topNodes.filter(node => edgeNodeIds.has(node._id));
    const qualityNodes = displayNodes.filter(node => node._articleCount > 1 || node._degree > 1);
    if (qualityNodes.length >= 4) {
      displayNodes = qualityNodes;
    }
    displayNodes = displayNodes
      .sort((a, b) => b._score - a._score)
      .slice(0, 10);

    if (displayNodes.length === 0 || graphEdges.length === 0) {
      this._graphNodes = [];
      this._graphEdges = [];
      this._graphNodeById = {};
      this._drawGraph();
      return;
    }

    allowedIds = new Set(displayNodes.map(node => node._id));
    graphEdges = graphEdges.filter(edge => allowedIds.has(edge.from) && allowedIds.has(edge.to));

    const W = this._graphW;
    const H = this._graphH;
    const adjacency = {};
    displayNodes.forEach(node => { adjacency[node._id] = new Set(); });
    graphEdges.forEach(edge => {
      adjacency[edge.from].add(edge.to);
      adjacency[edge.to].add(edge.from);
    });

    const nodeByRawId = displayNodes.reduce((map, node) => {
      map[node._id] = node;
      return map;
    }, {});
    const visited = new Set();
    const components = [];
    displayNodes.forEach(node => {
      if (visited.has(node._id)) return;
      const queue = [node._id];
      const ids = [];
      visited.add(node._id);
      while (queue.length) {
        const id = queue.shift();
        ids.push(id);
        (adjacency[id] || []).forEach(next => {
          if (visited.has(next)) return;
          visited.add(next);
          queue.push(next);
        });
      }
      components.push(ids.map(id => nodeByRawId[id]).sort((a, b) => b._degree - a._degree));
    });
    components.sort((a, b) => b.length - a.length);

    const cols = 1;
    const rows = Math.max(1, components.length);
    const cellW = W;
    const cellH = H / rows;
    const positioned = {};
    components.forEach((component, compIndex) => {
      const row = Math.floor(compIndex / cols);
      const col = compIndex % cols;
      const centerX = cellW * col + cellW / 2;
      const centerY = cellH * row + cellH / 2;
      const count = component.length;
      const radiusX = Math.max(92, Math.min(cellW * 0.34, 150));
      const radiusY = Math.max(42, Math.min(cellH * 0.28, 82));

      component.forEach((node, index) => {
        let x = centerX;
        let y = centerY;
        if (count === 2) {
          x = centerX + (index === 0 ? -radiusX : radiusX);
        } else if (count > 2) {
          const angle = -Math.PI / 2 + (index / count) * Math.PI * 2;
          x = centerX + Math.cos(angle) * radiusX;
          y = centerY + Math.sin(angle) * radiusY;
        }
        positioned[node._id] = {
          x: Math.max(36, Math.min(W - 36, x)),
          y: Math.max(36, Math.min(H - 36, y)),
          isCenter: index === 0
        };
      });
    });

    this._graphNodes = displayNodes.map((node) => {
      const id = node._id;
      const position = positioned[id] || { x: W * 0.5, y: H * 0.5, isCenter: false };

      const style = this._getGraphTypeStyle(node.type || node.entity_type);
      return {
        id,
        label: this._shortGraphLabel(node.label || id),
        fullLabel: node.label || id,
        type: node.type || node.entity_type || 'Unknown',
        description: node.description || '',
        x: position.x,
        y: position.y,
        r: position.isCenter ? 28 : (node._degree > 1 ? 23 : 20),
        color: style.color,
        stroke: style.stroke,
        isCenter: position.isCenter
      };
    });

    this._graphNodeById = this._graphNodes.reduce((map, node) => {
      map[node.id] = node;
      return map;
    }, {});

    this._graphEdges = graphEdges;
    this._drawGraph();
  },

  _startGraphAnimation() {
    if (this._graphAnimFrame) return;
    const loop = () => {
      this._graphPulse = (this._graphPulse + 0.02) % (Math.PI * 2);
      this._graphFlowOffset = (this._graphFlowOffset + 0.5) % 24;
      this._drawGraph();
      this._graphAnimFrame = this._graphCanvas.requestAnimationFrame(loop);
    };
    this._graphAnimFrame = this._graphCanvas.requestAnimationFrame(loop);
  },

  _stopGraphAnimation() {
    if (this._graphAnimFrame && this._graphCanvas) {
      this._graphCanvas.cancelAnimationFrame(this._graphAnimFrame);
    }
    this._graphAnimFrame = null;
  },

  _drawGraph() {
    const ctx = this._graphCtx;
    const W = this._graphW;
    const H = this._graphH;
    if (!ctx) return;
    const nodes = this._graphNodes || [];
    const edges = this._graphEdges || [];
    const nodeById = this._graphNodeById || {};
    const pulse = this._graphPulse || 0;

    const hexToRgb = (hex) => {
      const value = String(hex || '#ffffff').replace('#', '');
      return {
        r: parseInt(value.slice(0, 2), 16) || 255,
        g: parseInt(value.slice(2, 4), 16) || 255,
        b: parseInt(value.slice(4, 6), 16) || 255
      };
    };

    const drawGlow = (x, y, radius, color, alpha) => {
      const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
      gradient.addColorStop(0, color);
      gradient.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    };

    // 背景
    const bg = ctx.createRadialGradient(W / 2, H / 2, 0, W / 2, H / 2, W * 0.7);
    bg.addColorStop(0, '#1e1b4b');
    bg.addColorStop(1, '#0f0e17');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);
    drawGlow(W * 0.28, H * 0.28, Math.max(W, H) * 0.42, 'rgba(96,165,250,0.18)', 1);
    drawGlow(W * 0.76, H * 0.30, Math.max(W, H) * 0.36, 'rgba(52,211,153,0.14)', 1);
    drawGlow(W * 0.50, H * 0.84, Math.max(W, H) * 0.34, 'rgba(244,114,182,0.12)', 1);
    ctx.save();
    ctx.globalAlpha = 0.08;
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 8]);
    ctx.beginPath();
    ctx.arc(W / 2, H / 2, Math.min(W, H) * 0.36, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(W / 2, H / 2, Math.min(W, H) * 0.22, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    if (!nodes.length) return;

    // 连线
    edges.forEach((edge, edgeIndex) => {
      const from = nodeById[edge.from];
      const to = nodeById[edge.to];
      if (!from || !to) return;

      // 计算连线端点（从节点边缘出发）
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist === 0) return;
      const ux = dx / dist;
      const uy = dy / dist;
      const x1 = from.x + ux * from.r;
      const y1 = from.y + uy * from.r;
      const x2 = to.x - ux * to.r;
      const y2 = to.y - uy * to.r;
      const angle = Math.atan2(y2 - y1, x2 - x1);
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;

      ctx.save();
      ctx.strokeStyle = edge.color;
      ctx.lineCap = 'round';
      ctx.lineWidth = edge.width || 1.5;
      ctx.globalAlpha = 0.78;
      ctx.setLineDash([6, 6]);
      ctx.lineDashOffset = -(this._graphFlowOffset || 0);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();

      // 箭头
      ctx.setLineDash([]);
      ctx.globalAlpha = 0.85;
      const arrowLen = 8;
      ctx.beginPath();
      ctx.moveTo(x2, y2);
      ctx.lineTo(x2 - arrowLen * Math.cos(angle - 0.4), y2 - arrowLen * Math.sin(angle - 0.4));
      ctx.lineTo(x2 - arrowLen * Math.cos(angle + 0.4), y2 - arrowLen * Math.sin(angle + 0.4));
      ctx.closePath();
      ctx.fillStyle = edge.color;
      ctx.fill();

      // 关系标签：贴着线旋转，尽量还原 demo 风格。
      if (edge.label) {
        const labelX = (x1 + x2) / 2;
        const labelY = (y1 + y2) / 2;
        let labelAngle = angle;
        let labelOffset = edgeIndex % 2 === 0 ? -10 : 10;
        if (labelAngle > Math.PI / 2 || labelAngle < -Math.PI / 2) {
          labelAngle += Math.PI;
          labelOffset = -labelOffset;
        }
        ctx.save();
        ctx.translate(labelX, labelY);
        ctx.rotate(labelAngle);
        ctx.font = 'bold 7px sans-serif';
        ctx.fillStyle = edge.textColor || edge.color;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(edge.label, 0, labelOffset);
        ctx.restore();
      }

      ctx.restore();
    });

    // 节点
    nodes.forEach(node => {
      const isCenter = !!node.isCenter;
      const rgb = hexToRgb(node.color);

      ctx.save();

      // 雷达波纹
      const pulseR = node.r * (1 + Math.sin(pulse) * 0.34 + 0.38);
      ctx.beginPath();
      ctx.arc(node.x, node.y, pulseR, 0, Math.PI * 2);
      ctx.strokeStyle = node.stroke;
      ctx.lineWidth = isCenter ? 2 : 1.2;
      ctx.globalAlpha = Math.max(0, 0.4 - (pulseR - node.r) / (node.r * 0.8) * 0.45);
      ctx.stroke();

      // 旋转外环（虚线）
      ctx.save();
      ctx.translate(node.x, node.y);
      ctx.rotate(pulse * (isCenter ? 0.5 : 0.3));
      ctx.beginPath();
      ctx.arc(0, 0, node.r + 8, 0, Math.PI * 2);
      ctx.strokeStyle = node.stroke;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.35;
      ctx.setLineDash([4, 6]);
      ctx.stroke();
      ctx.restore();

      if (isCenter) {
        drawGlow(node.x, node.y, node.r * 2.2, node.color, 0.9);
      }

      // 节点主体
      ctx.globalAlpha = 1;
      const fill = ctx.createRadialGradient(
        node.x - node.r * 0.25,
        node.y - node.r * 0.25,
        node.r * 0.2,
        node.x,
        node.y,
        node.r * 1.15
      );
      fill.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},0.92)`);
      fill.addColorStop(0.72, `rgba(${rgb.r},${rgb.g},${rgb.b},0.55)`);
      fill.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0.28)`);
      ctx.shadowColor = node.color;
      ctx.shadowBlur = isCenter ? 22 : 14;
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
      ctx.fillStyle = fill;
      ctx.fill();
      ctx.strokeStyle = node.stroke;
      ctx.lineWidth = isCenter ? 2.4 : 1.4;
      ctx.stroke();

      if (isCenter) {
        ctx.shadowBlur = 0;
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r * 0.46, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.12)';
        ctx.fill();
      }

      // 节点文字
      ctx.fillStyle = '#ffffff';
      ctx.font = `bold ${isCenter ? 13 : 9}px sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.shadowColor = 'rgba(255,255,255,0.55)';
      ctx.shadowBlur = isCenter ? 5 : 3;
      ctx.fillText(node.label, node.x, node.y);
      ctx.shadowBlur = 0;

      ctx.restore();
    });
  },

  // Touch 事件：点击节点
  onGraphTouchStart(e) {
    if (!this._graphNodes) return;
    const touch = e.touches[0];
    const point = this._getGraphTouchPoint(touch);
    const x = point.x;
    const y = point.y;
    // 找到被点击的节点
    for (let i = this._graphNodes.length - 1; i >= 0; i--) {
      const node = this._graphNodes[i];
      const dx = x - node.x;
      const dy = y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.r + 8) {
        this._graphDragNode = node;
        return;
      }
    }
    this._graphDragNode = null;
  },

  onGraphTouchEnd() {
    if (this._graphDragNode) {
      const name = this._graphDragNode.id;
      this._graphDragNode = null;
      this.openEntityDetail({ currentTarget: { dataset: { name } } });
      return;
    }
    this._graphDragNode = null;
  },

  // --- Graph 页面相关方法 ---

  // 切换 Graph 标签页 (Network vs Trends)
  switchGraphTab(e) {
    const tab = e.currentTarget.dataset.tab;
    this.setData({ activeGraphTab: tab });
    if (tab === 'trends') {
      // 切到 trends 时停止 canvas 动画，释放 GPU/内存
      this._stopGraphAnimation();
      if (this.data.trendsTopics.length === 0) {
        // topics 还没有，先加载实体（加载完后会自动设置 topics 并触发 trends）
        if (this.data.trendingEntities.length > 0) {
          // 实体已有但 topics 未设置，直接从实体里取（去重）
          const topics = [...new Set(this.data.trendingEntities.slice(0, 8).map(e => e.entity_name))];
          this.setData({ trendsTopics: topics, activeTrendsTopic: topics[0] });
          this.fetchTrendsData();
        } else {
          this._fetchTrendingEntitiesForTopics();
        }
      } else if (this.data.trendsData.length === 0) {
        this.fetchTrendsData();
      }
    } else if (tab === 'network') {
      // 切回 network 时，wx:if 导致 canvas DOM 已销毁重建，必须清掉旧引用强制重新初始化
      this._graphCanvas = null;
      this._graphCtx = null;
      setTimeout(() => { this._initGraphCanvas(); }, 100);
    }
  },

  // 专门为 trends topics 加载实体（不影响 network tab 的 trendingEntities 状态）
  _fetchTrendingEntitiesForTopics() {
    this.setData({ trendsLoading: true });
    wx.request({
      url: `${this.data.baseUrl}/api/knowledge-graph/trending-entities`,
      data: { days: 7, limit: 8 },
      success: (res) => {
        if (res.data && res.data.success) {
          const entities = res.data.data.entities || [];
          if (entities.length > 0) {
            const topics = [...new Set(entities.map(e => e.entity_name))];
            const defaultTopic = topics[0];
            this.setData({ trendsTopics: topics, activeTrendsTopic: defaultTopic });
            this.fetchTrendsData();
          } else {
            this.setData({ trendsLoading: false });
          }
        } else {
          this.setData({ trendsLoading: false });
        }
      },
      fail: () => { this.setData({ trendsLoading: false }); }
    });
  },

  // 获取知识图谱数据（全局视角）
  _requestGraphDataByTopic(topic) {
    return new Promise((resolve) => {
      wx.request({
        url: `${this.data.baseUrl}/api/knowledge-graph/entities`,
        data: { topic },
        success: (res) => {
          if (res.data && res.data.success) {
            resolve(res.data.data || { nodes: [], edges: [] });
          } else {
            resolve({ nodes: [], edges: [] });
          }
        },
        fail: () => {
          resolve({ nodes: [], edges: [] });
        }
      });
    });
  },

  fetchGraphData(topic) {
    // Entity Network intentionally uses the static demo graph.
    if (this.data.activeGraphTab === 'network') {
      this.setData({ graphLoading: false });
      this._initMockGraphData();
      return;
    }

    const topics = this._getGraphTopics(topic);
    this.setData({ graphLoading: true });

    Promise.all(topics.map(t => this._requestGraphDataByTopic(t))).then(results => {
      const nodeMap = {};
      const edgeMap = {};
      results.forEach(data => {
        (data.nodes || []).forEach(node => {
          const id = node.id || node.label;
          if (!id || nodeMap[id]) return;
          nodeMap[id] = node;
        });
        (data.edges || []).forEach(edge => {
          const from = edge.source || edge.from;
          const to = edge.target || edge.to;
          if (!from || !to) return;
          const relation = edge.relation || edge.label || '';
          const key = `${from}__${to}__${relation}`;
          if (!edgeMap[key]) edgeMap[key] = edge;
        });
      });

      this.setData({
        graphNodes: Object.values(nodeMap),
        graphEdges: Object.values(edgeMap),
        graphLoading: false
      }, () => {
        this._syncGraphCanvasData();
      });
    });
  },

  // 获取热门实体排行
  fetchTrendingEntities() {
    wx.request({
      url: `${this.data.baseUrl}/api/knowledge-graph/trending-entities`,
      data: { days: 7, limit: 10 },
      success: (res) => {
        if (res.data && res.data.success) {
          const entities = res.data.data.entities || [];
          // 为每个实体添加样式和图标
          const formatted = entities.map((item, index) => {
            const type = (item.entity_type || 'Unknown').toLowerCase();
            let color = 'blue';
            let icon = 'ph-circle';

            if (type === 'person') {
              color = 'purple';
              icon = 'ph-user';
            } else if (type === 'organization') {
              color = 'blue';
              icon = 'ph-buildings';
            } else if (type === 'concept') {
              color = 'green';
              icon = 'ph-lightbulb';
            } else if (type === 'location') {
              color = 'orange';
              icon = 'ph-map-pin';
            }

            return {
              ...item,
              rank: index + 1,
              color,
              icon,
              trend: index < 3 ? 'up' : (index > 7 ? 'down' : 'stable')
            };
          });
          this.setData({ trendingEntities: formatted });

          // 用真实热门实体名替换硬编码的 trendsTopics
          if (formatted.length > 0) {
            const topics = [...new Set(formatted.slice(0, 8).map(e => e.entity_name))];
            const defaultTopic = topics[0];
            this.setData({
              trendsTopics: topics,
              activeTrendsTopic: defaultTopic
            });
            // 如果用户已经在 trends tab，自动触发数据加载
            if (this.data.activeGraphTab === 'trends' && this.data.trendsData.length === 0) {
              this.fetchTrendsData();
            }
          }
        }
      },
      fail: () => {}
    });
  },

  // 获取趋势数据（Heat Trends 标签页）
  fetchTrendsData() {
    this.setData({ trendsLoading: true });
    wx.request({
      url: `${this.data.baseUrl}/api/knowledge-graph/trends`,
      data: { topic: this.data.activeTrendsTopic },
      success: (res) => {
        if (res.data && res.data.success) {
          const raw = res.data.data.trends || [];
          this._processTrendsData(raw, res.data.data.insight || '');
        } else {
          this.setData({ trendsLoading: false });
        }
      },
      fail: () => {
        this.setData({ trendsLoading: false });
      }
    });
  },

  // 处理趋势数据：归一化 bar 高度、计算统计数字、提取日期标签
  _processTrendsData(raw, insight) {
    if (!raw || raw.length === 0) {
      this.setData({ trendsData: [], trendsTotalMentions: 0, trendsDelta: 0, trendsDeltaAbs: 0, trendsInsight: insight, trendsLoading: false });
      return;
    }

    // 限制最多显示 14 条，防止柱子过窄和数据量过大
    const data = raw.slice(-14);

    const maxCount = Math.max(...data.map(d => d.count || 0), 1);
    const maxBarH = 180; // rpx，保守值，不超出 chart-bars 的 240rpx
    const peakIdx = data.reduce((best, d, i) => (d.count > data[best].count ? i : best), 0);

    // Keep x-axis labels sparse so adjacent dates do not overlap.
    const labelStep = Math.max(3, Math.ceil(data.length / 4));
    const labelIndexes = [];
    const addLabelIndex = (index, force = false) => {
      if (index < 0 || index >= data.length) return;
      if (labelIndexes.length === 0) {
        labelIndexes.push(index);
        return;
      }
      const last = labelIndexes[labelIndexes.length - 1];
      if (index - last >= 2) {
        labelIndexes.push(index);
      } else if (force) {
        labelIndexes[labelIndexes.length - 1] = index;
      }
    };
    for (let i = 0; i < data.length - 1; i += labelStep) {
      addLabelIndex(i);
    }
    addLabelIndex(data.length - 1, true);
    const labelIndexSet = new Set(labelIndexes);

    const processed = data.map((d, i) => ({
      ...d,
      barHeight: Math.max(16, Math.round((d.count / maxCount) * maxBarH)),
      isPeak: i === peakIdx,
      label: labelIndexSet.has(i) ? this._formatTrendsDate(d.date || '') : ''
    }));

    // Compare the latest day with the previous day.
    const today = data[data.length - 1] || {};
    const yesterday = data[data.length - 2] || {};
    const todayCount = Number(today.count || 0);
    const yesterdayCount = Number(yesterday.count || 0);
    const delta = yesterdayCount > 0
      ? Math.round(((todayCount - yesterdayCount) / yesterdayCount) * 100)
      : (todayCount > 0 ? 100 : 0);

    const autoInsight = insight || (data.length > 0
      ? `"${this.data.activeTrendsTopic}" peaked on ${this._formatTrendsDate(data[peakIdx].date)} with ${data[peakIdx].count} mentions.`
      : '');

    this.setData({
      trendsData: processed,
      trendsTotalMentions: todayCount,
      trendsDelta: delta,
      trendsDeltaAbs: Math.abs(delta),
      trendsInsight: autoInsight,
      trendsLoading: false
    });
  },

  _formatTrendsDate(dateStr) {
    if (!dateStr) return '';
    const safe = dateStr.replace('T', ' ').replace(/-/g, '/');
    const d = new Date(safe);
    if (isNaN(d.getTime())) return dateStr.slice(5, 10) || dateStr;
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${m}/${day}`;
  },

  // 切换 Trends topic
  switchTrendsTopic(e) {
    const topic = e.currentTarget.dataset.topic;
    if (topic === this.data.activeTrendsTopic) return;
    this.setData({ activeTrendsTopic: topic, trendsData: [] });
    this.fetchTrendsData();
  },

  // 打开实体详情弹窗（支持从图谱节点或排行列表触发）
  openEntityDetail(e) {
    const name = e.currentTarget.dataset.name;
    if (!name) return;

    // 优先从 trendingEntities 取样式信息
    const entity = this.data.trendingEntities.find(item => item.entity_name === name);
    // 从 graphNodes 取描述
    const node = this.data.graphNodes.find(n => n.id === name || n.label === name);

    // 根据 entity_type 推断颜色和图标
    const typeRaw = (entity && entity.entity_type) || (node && node.type) || 'Unknown';
    const type = typeRaw.toLowerCase();
    let color = 'blue';
    let icon = 'ph-circle';
    if (type === 'person') { color = 'purple'; icon = 'ph-user'; }
    else if (type === 'organization') { color = 'blue'; icon = 'ph-buildings'; }
    else if (type === 'concept') { color = 'green'; icon = 'ph-lightbulb'; }
    else if (type === 'location') { color = 'orange'; icon = 'ph-map-pin'; }

    this.setData({
      selectedEntity: {
        name,
        type: typeRaw,
        description: (node && node.description) || 'No description available.',
        color: (entity && entity.color) || color,
        icon: (entity && entity.icon) || icon,
        articleCount: entity ? entity.article_count : 0,
        articles: [],
        articlesLoading: true
      },
      showEntityDetail: true
    });

    // 异步加载相关文章
    this._fetchEntityArticles(name);
  },

  // 加载实体相关文章
  _fetchEntityArticles(entityName) {
    wx.request({
      url: `${this.data.baseUrl}/api/knowledge-graph/entity-articles`,
      data: { entity: entityName, limit: 5 },
      success: (res) => {
        if (res.data && res.data.success) {
          const articles = this._formatNewsList(res.data.data.list || []);
          const entity = this.data.selectedEntity;
          if (entity && entity.name === entityName) {
            this.setData({
              'selectedEntity.articles': articles,
              'selectedEntity.articlesLoading': false
            });
          }
        } else {
          this.setData({ 'selectedEntity.articlesLoading': false });
        }
      },
      fail: () => {
        this.setData({ 'selectedEntity.articlesLoading': false });
      }
    });
  },

  // 从实体详情跳转到新闻详情
  goToDetailFromEntity(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    this.setData({ showEntityDetail: false });
    setTimeout(() => { this.fetchNewsDetail(id); }, 300);
  },

  // Read Articles 按钮：跳转到首页并搜索该实体
  readEntityArticles() {
    const name = this.data.selectedEntity && this.data.selectedEntity.name;
    if (!name) return;
    this.setData({
      showEntityDetail: false,
      currentTab: 'home',
      searchQuery: name,
      isSearching: true,
      searchResults: [],
      searchPage: 1,
      searchHasMore: false
    });
    setTimeout(() => { this._doSearch(name, true); }, 300);
  },

  // 关闭实体详情弹窗
  closeEntityDetail() {
    this.setData({ showEntityDetail: false });
  },

  // See All：展示全部实体（复用搜索跳转到首页）
  toggleAllEntities() {
    this.setData({
      showEntityDetail: false,
      currentTab: 'home'
    });
    wx.showToast({ title: 'Showing all entities', icon: 'none', duration: 1500 });
  },

  // --- 登录 / 用户 ---

  openProfileModal() {
    this.setData({ showProfileModal: true });
  },

  closeProfileModal() {
    this.setData({ showProfileModal: false });
  },

  wxLogin() {
    if (this.data.loginLoading) return;
    this.setData({ loginLoading: true });
    wx.login({
      success: (res) => {
        console.log('[wx.login] response =', res);
        if (!res.code) {
          this.setData({ loginLoading: false });
          wx.showToast({ title: 'Login failed', icon: 'none' });
          return;
        }
        wx.request({
          url: `${this.data.baseUrl}/api/auth/login`,
          method: 'POST',
          header: { 'Content-Type': 'application/json' },
          data: { code: res.code },
          success: (r) => {
            console.log('[auth/login] response =', r);
            if (r.data && r.data.success) {
              const { openid, user } = r.data.data;
              app.globalData.openid = openid;
              wx.setStorageSync('openid', openid);
              wx.setStorageSync('userInfo', user);
              this.setData({ userInfo: user, loginLoading: false });
              this.fetchReadingHistory();
              
            } else {
              this.setData({ loginLoading: false });
              wx.showToast({ title: 'Login failed', icon: 'none' });
            }
          },
          fail: () => {
            this.setData({ loginLoading: false });
            wx.showToast({ title: 'Network error', icon: 'none' });
          }
        });
      },
      fail: () => {
        this.setData({ loginLoading: false });
        wx.showToast({ title: 'WeChat login error', icon: 'none' });
      }
    });
  },

  logout() {
    wx.removeStorageSync('openid');
    wx.removeStorageSync('userInfo');
    app.globalData.openid = null;
    this.setData({ userInfo: null, readingHistory: [], showProfileModal: false });
  },

  fetchReadingHistory() {
    const openid = app.globalData.openid;
    if (!openid) return;
    this.setData({ historyLoading: true });
    wx.request({
      url: `${this.data.baseUrl}/api/auth/history`,
      data: { user_id: openid, page: 1, page_size: 50 },
      success: (res) => {
        if (res.data && res.data.success) {
          const list = this._formatNewsList(res.data.data.list || []).map(item => {
            item.formatted_read_at = this.formatTimeAgo(item.read_at);
            return item;
          });
          this.setData({ readingHistory: list, historyLoading: false });
        } else {
          this.setData({ historyLoading: false });
        }
      },
      fail: () => { this.setData({ historyLoading: false }); }
    });
  }
})
