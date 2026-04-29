// app.js
App({
  onLaunch() {},
  globalData: {
    wechatId: wx.getStorageSync('wechatId') || '',
  }
})
