Page({
  data: {
    url: ''
  },
  onLoad(options) {
    if (options.url) {
      let url = decodeURIComponent(options.url).trim();
      if (url.startsWith('//')) url = `https:${url}`;
      if (!/^[a-zA-Z][a-zA-Z\d+\-.]*:\/\//.test(url) && /^[\w.-]+\.[a-z]{2,}([/?#].*)?$/i.test(url)) {
        url = `https://${url}`;
      }
      this.setData({ url });
    }
  },
  goBack() {
    wx.navigateBack();
  }
})
