// schedule.js
let appConfig = {}
try {
  appConfig = require('../../config.local')
} catch (e) {
  appConfig = require('../../config.example')
}

const { hmacSha1Base64 } = require('../../utils/hmac_sha1')
const DEFAULT_API    = appConfig.API_BASE_URL || 'http://127.0.0.1:17800'
const OSS_CONFIG     = appConfig.OSS || {}
const OSS_BUCKET     = OSS_CONFIG.BUCKET || ''
const OSS_ENDPOINT   = OSS_CONFIG.ENDPOINT || ''
const OSS_PREFIX     = OSS_CONFIG.PREFIX || ''
const OSS_KEY_ID     = OSS_CONFIG.ACCESS_KEY_ID || ''
const OSS_KEY_SECRET = OSS_CONFIG.ACCESS_KEY_SECRET || ''

function ossUpload(filePath, objectKey) {
  return new Promise((resolve, reject) => {
    if (!OSS_BUCKET || !OSS_ENDPOINT || !OSS_KEY_ID || !OSS_KEY_SECRET) {
      reject(new Error('OSS config is missing. Run python scripts/setup_config.py after filling .env.'))
      return
    }
    wx.getFileSystemManager().readFile({
      filePath,
      success: ({ data: fileData }) => {
        const date = new Date().toUTCString()
        const contentType = 'image/jpeg'
        const stringToSign = `PUT\n\n${contentType}\n${date}\n/${OSS_BUCKET}/${objectKey}`
        const sig = hmacSha1Base64(OSS_KEY_SECRET, stringToSign)
        wx.request({
          url: `https://${OSS_BUCKET}.${OSS_ENDPOINT}/${objectKey}`,
          method: 'PUT',
          data: fileData,
          header: {
            'Content-Type': contentType,
            'Date': date,
            'Authorization': `OSS ${OSS_KEY_ID}:${sig}`,
          },
          success: res => (res.statusCode === 200 ? resolve(res) : reject(res)),
          fail: reject,
        })
      },
      fail: reject,
    })
  })
}

// ── Helpers ────────────────────────────────────────────────────────

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

function dateKey(d) {
  const [day, mon] = d.split('-')
  return MONTHS.indexOf(mon) * 100 + parseInt(day)
}

function getTodayStr() {
  const now = new Date()
  return `${now.getDate()}-${MONTHS[now.getMonth()]}`
}

const TIME_ORDER = [
  '08:00-09:35','09:50-11:25','11:30-12:15',
  '13:00-14:35','13:50-14:35',
  '14:45-16:25','16:35-17:20','16:35-18:10',
  '17:25-18:10','18:30-19:15',
]

function timeToMins(t) {
  const [h, m] = t.split(':').map(Number)
  return h * 60 + m
}

function parseSlot(slot) {
  const dash = slot.lastIndexOf('-')
  return { start: timeToMins(slot.slice(0, dash)), end: timeToMins(slot.slice(dash + 1)) }
}

function getScrollTargetIdx(classes) {
  if (!classes.length) return 0
  const cur = new Date().getHours() * 60 + new Date().getMinutes()
  const times = [...new Set(classes.map(c => c.time))].sort((a, b) => {
    const ai = TIME_ORDER.indexOf(a), bi = TIME_ORDER.indexOf(b)
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
  })
  for (const t of times) {
    const { start, end } = parseSlot(t)
    if (cur >= start && cur <= end) return classes.findIndex(c => c.time === t)
  }
  let target = times[0]
  for (const t of times) {
    if (parseSlot(t).start <= cur) target = t
  }
  return classes.findIndex(c => c.time === target)
}

// PATCH /records/{id}
function apiPatch(apiUrl, id, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${apiUrl}/records/${id}`,
      method: 'PATCH',
      data,
      header: { 'Content-Type': 'application/json' },
      success: res => (res.statusCode === 200 ? resolve(res.data) : reject(res)),
      fail: reject,
    })
  })
}

// PATCH /records/{id}/attrs
function apiAttrs(apiUrl, id, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${apiUrl}/records/${id}/attrs`,
      method: 'PATCH',
      data,
      header: { 'Content-Type': 'application/json' },
      success: res => (res.statusCode === 200 ? resolve(res.data) : reject(res)),
      fail: reject,
    })
  })
}

// ── Page ───────────────────────────────────────────────────────────

let _lastTapTime     = 0
let _lastTapIdx      = -1
let _nickTapTimer    = null

let _totalTapCount   = 0
let _totalTapTimer   = null


Page({
  data: {
    dateList: [],
    dateRaw: [],
    dateIndex: 0,
    displayDate: '选择日期',
    classes: [],
    selectedIdx: -1,
    selectedRecord: null,
    hasResult: false,
    scrollIntoView: '',
    showInputModal: false,
    inputCount: '',
    showLoginModal: false,
    inputName: '',
    wechatId: '',
    apiUrl: DEFAULT_API,
    showRefModal: false,
    refRecord: null,
    refMatchLevel: 0,
    syncFromRef: false,
    refHistoricalCount: 0,
    showRemarkModal: false,
    inputRemark: '',
    showHiddenItems: false,
    showVisibilityModal: false,
    showEditModal: false,
    editRoom: '',
    editDate: '',
    editTime: '',
  },

  onLoad() {
    const wechatId = getApp().globalData.wechatId || ''
    const apiUrl = wx.getStorageSync('apiUrl') || DEFAULT_API
    this.setData({ wechatId, showLoginModal: !wechatId, apiUrl })
    wx.showLoading({ title: '加载中...' })
    wx.request({
      url: `${apiUrl}/dates`,
      method: 'GET',
      success: res => {
        const dateRaw = res.data
          .sort((a, b) => dateKey(a.date) - dateKey(b.date))
        const dateList = dateRaw.map(d => `${d.date} ${d.day}`)
        const today = getTodayStr()
        let dateIndex = dateRaw.findIndex(d => d.date === today)
        if (dateIndex === -1) {
          const todayKey = dateKey(today)
          const nextIdx = dateRaw.findIndex(d => dateKey(d.date) > todayKey)
          dateIndex = nextIdx !== -1 ? nextIdx : Math.max(0, dateRaw.length - 1)
        }
        const entry = dateRaw[dateIndex]
        this.setData({
          dateRaw, dateList, dateIndex,
          displayDate: entry ? `${entry.date} ${entry.day}` : '选择日期',
        })
        wx.hideLoading()
        if (entry) this.onQuery()
      },
      fail: err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '加载失败', icon: 'error' })
      },
    })
  },

  onDateChange(e) {
    const dateIndex = parseInt(e.detail.value)
    const entry = this.data.dateRaw[dateIndex]
    this.setData({ dateIndex, displayDate: `${entry.date} ${entry.day}` })
    this.onQuery()
  },

  onPickerLongPress() {
    this._jumpToUnfilledDate()
  },

  async _jumpToUnfilledDate() {
    const { dateRaw, apiUrl } = this.data
    const todayKey = dateKey(getTodayStr())
    const currentDate = dateRaw[this.data.dateIndex] && dateRaw[this.data.dateIndex].date
    const pastDates = dateRaw
      .map((d, i) => ({ ...d, i }))
      .filter(d => dateKey(d.date) < todayKey && d.date !== '2-Mar' && d.date !== currentDate)
      .reverse()

    if (!pastDates.length) {
      wx.showToast({ title: '没有未填完的日期', icon: 'none' })
      return
    }

    wx.showLoading({ title: '查找中...' })
    for (const d of pastDates) {
      const records = await new Promise(res =>
        wx.request({
          url: `${apiUrl}/records`,
          method: 'GET',
          data: { date: d.date },
          success: r => res(Array.isArray(r.data) ? r.data : []),
          fail: () => res([]),
        })
      )
      if (records.some(r => !r.hidden && (!r.by || !r.photoUploaded))) {
        wx.hideLoading()
        this.setData({ dateIndex: d.i, displayDate: `${d.date} ${d.day}` })
        this.onQuery()
        return
      }
    }
    wx.hideLoading()
    wx.showToast({ title: '没有未填完的日期', icon: 'none' })
  },

  _buildPhotoUrl(dateStr, timeStr, room) {
    const [dd, monStr] = dateStr.split('-')
    const mo = MONTHS.indexOf(monStr) + 1
    const startStr = timeStr.slice(0, timeStr.lastIndexOf('-'))
    const [hh, mm] = startStr.split(':')
    const fileName = `${mo}.${dd}_${hh}.${mm}_${room}.jpg`
    return `https://${OSS_BUCKET}.${OSS_ENDPOINT}/${OSS_PREFIX}${fileName}`
  },

  onQuery() {
    const { dateRaw, dateIndex } = this.data
    const date = dateRaw[dateIndex] && dateRaw[dateIndex].date
    if (!date) return
    const { apiUrl } = this.data
    wx.showLoading({ title: '加载中...' })
    wx.request({
      url: `${apiUrl}/records`,
      method: 'GET',
      data: { date },
      success: res => {
        wx.hideLoading()
        const classes = res.data.map(r => ({
          id: r.id,
          index: r.indexNo,
          time: r.time,
          moduleCode: r.moduleCode,
          module: r.moduleName,
          lecturer: r.lecturer,
          room: r.room,
          remark: r.remark || '',
          totalStudentNum: r.totalStudentNum,
          studentNumInClassroom: r.studentNumInClassroom || 0,
          percent: r.percent || 0,
          by: r.by || '',
          photoUrl: this._buildPhotoUrl(date, r.time, r.room),
          hasPhoto: !!r.photoUploaded,
          photoExpanded: false,
          hidden: !!r.hidden,
          _show: !r.hidden || this.data.showHiddenItems,
        }))
        const targetIdx = getScrollTargetIdx(classes)
        this.setData({
          classes,
          selectedIdx: targetIdx,
          selectedRecord: classes[targetIdx] || null,
          hasResult: true,
          scrollIntoView: `item-${targetIdx}`,
        })
        this._syncPhotos(classes)
      },
      fail: err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '查询失败', icon: 'error' })
      },
    })
  },

  onPhotoLoad(e) {
    const idx = e.currentTarget.dataset.idx
    const rec = this.data.classes[idx]
    const update = { [`classes[${idx}].hasPhoto`]: true }
    if (this.data.selectedIdx === idx) {
      update.selectedRecord = { ...this.data.selectedRecord, hasPhoto: true }
    }
    this.setData(update)
    // 图片存在但 DB 未标记，自动修正
    if (rec && !rec.hasPhoto) {
      apiPatch(this.data.apiUrl, rec.id, { photoUploaded: true })
        .then(() => console.log('[photoLoad] DB updated to true, id=', rec.id))
        .catch(err => console.error('[photoLoad] DB update failed', err))
    }
  },

  onPhotoError(e) {
    const idx = e.currentTarget.dataset.idx
    const rec = this.data.classes[idx]
    console.log('[photoError] idx=', idx, 'url=', rec && rec.photoUrl)
    const update = { [`classes[${idx}].hasPhoto`]: false }
    if (this.data.selectedIdx === idx) {
      update.selectedRecord = { ...this.data.selectedRecord, hasPhoto: false }
    }
    this.setData(update)
    // 只有 DB 里标记为 true 时才往回修正，避免对未上传的记录发无效请求
    if (rec && rec.hasPhoto) {
      console.log('[photoError] DB marked true but image missing, correcting. id=', rec.id)
      apiPatch(this.data.apiUrl, rec.id, { photoUploaded: false })
        .catch(err => console.error('[photoError] DB update failed', err))
    }
  },

  onSelectRow(e) {
    const idx = e.currentTarget.dataset.idx
    const now = Date.now()
    if (idx === _lastTapIdx && now - _lastTapTime < 300) {
      _lastTapTime = 0
      _lastTapIdx  = -1
      const cur = this.data.classes[idx]
      this.setData({ showRemarkModal: true, inputRemark: cur.remark || '', selectedIdx: idx, selectedRecord: cur })
      return
    }
    _lastTapTime = now
    _lastTapIdx  = idx
    const cur = this.data.classes[idx]
    const photoExpanded = !cur.photoExpanded
    this.setData({
      selectedIdx: idx,
      selectedRecord: cur,
      [`classes[${idx}].photoExpanded`]: photoExpanded,
    })
  },

  onPreviewPhoto(e) {
    const idx = e.currentTarget.dataset.idx
    const item = this.data.classes[idx]
    this.setData({ [`classes[${idx}].photoExpanded`]: false })
    wx.previewImage({ current: item.photoUrl, urls: [item.photoUrl] })
  },

  onNameInput(e) {
    this.setData({ inputName: e.detail.value })
  },

  onConfirmName() {
    const name = this.data.inputName.trim()
    if (name !== 'Ruizhe' && name !== 'Shuyue') {
      wx.showToast({ title: '用户名不正确', icon: 'error' })
      return
    }
    getApp().globalData.wechatId = name
    wx.setStorageSync('wechatId', name)
    this.setData({ wechatId: name, showLoginModal: false, inputName: '' })
  },

  onFillCount() {
    if (!this.data.wechatId) {
      wx.showToast({ title: '请先完成登录', icon: 'none' })
      return
    }
    if (!this.data.selectedRecord) {
      wx.showToast({ title: '请先选择一条记录', icon: 'none' })
      return
    }
    this.setData({ showInputModal: true, inputCount: '' })
  },

  onCountInput(e) {
    this.setData({ inputCount: e.detail.value })
  },

  onCancelInput() {
    this.setData({ showInputModal: false, inputCount: '', syncFromRef: false, refHistoricalCount: 0 })
  },

  onConfirmInput() {
    const count = parseInt(this.data.inputCount)
    if (isNaN(count) || count < 0) {
      wx.showToast({ title: '请输入有效人数', icon: 'none' })
      return
    }
    const rec = this.data.selectedRecord
    const total = rec.totalStudentNum
    const percent = total > 0 ? parseFloat((count / total * 100).toFixed(1)) : 0
    const wechatId = this.data.wechatId
    console.log('[PATCH]', rec.id, { studentNumInClassroom: count, percent, by: wechatId })
    wx.showLoading({ title: '提交中...' })
    const syncFromRef = this.data.syncFromRef
    const refRecord = this.data.refRecord
    apiPatch(this.data.apiUrl, rec.id, { studentNumInClassroom: count, percent, by: wechatId })
      .then(() => {
        wx.hideLoading()
        const idx = this.data.selectedIdx
        const classes = this.data.classes.map((c, i) =>
          i === idx ? { ...c, studentNumInClassroom: count, percent, by: wechatId } : c
        )
        const selectedRecord = { ...rec, studentNumInClassroom: count, percent, by: wechatId }
        this.setData({ classes, selectedRecord, showInputModal: false, inputCount: '', syncFromRef: false, refHistoricalCount: 0 })
        wx.showToast({ title: '提交成功', icon: 'success' })
        if (syncFromRef && refRecord) {
          const dateStr = this.data.dateRaw[this.data.dateIndex].date
          const [dd, monStr] = dateStr.split('-')
          const mo = MONTHS.indexOf(monStr) + 1
          const startStr = rec.time.slice(0, rec.time.lastIndexOf('-'))
          const [hh, mm] = startStr.split(':')
          const fileName = `${mo}.${dd}_${hh}.${mm}_${rec.room}.jpg`
          wx.downloadFile({
            url: refRecord.photoUrl,
            success: dlRes => {
              if (dlRes.statusCode !== 200) return
              ossUpload(dlRes.tempFilePath, OSS_PREFIX + fileName)
                .then(() => apiPatch(this.data.apiUrl, rec.id, { photoUploaded: true }))
                .then(() => {
                  const i = this.data.selectedIdx
                  const sr = { ...this.data.selectedRecord, hasPhoto: true }
                  this.setData({ [`classes[${i}].hasPhoto`]: true, selectedRecord: sr })
                })
                .catch(err => console.error('[syncPhoto] failed', err))
            },
          })
        }
      })
      .catch(err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '提交失败', icon: 'error' })
      })
  },

  onUploadPhoto() {
    if (!this.data.wechatId) {
      wx.showToast({ title: '请先完成登录', icon: 'none' })
      return
    }
    if (!this.data.selectedRecord) {
      wx.showToast({ title: '请先选择一条记录', icon: 'none' })
      return
    }
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const filePath = res.tempFiles[0].tempFilePath
        const rec = this.data.selectedRecord
        const dateStr = this.data.dateRaw[this.data.dateIndex].date
        const [dd, monStr] = dateStr.split('-')
        const mo = MONTHS.indexOf(monStr) + 1
        const startStr = rec.time.slice(0, rec.time.lastIndexOf('-'))
        const [hh, mm] = startStr.split(':')
        const fileName = `${mo}.${dd}_${hh}.${mm}_${rec.room}.jpg`
        wx.showLoading({ title: '上传中...' })
        ossUpload(filePath, OSS_PREFIX + fileName)
          .then(() => {
            const idx = this.data.selectedIdx
            const rec = this.data.classes[idx]
            return apiPatch(this.data.apiUrl, rec.id, { photoUploaded: true }).then(() => idx)
          })
          .then(idx => {
            wx.hideLoading()
            const selectedRecord = { ...this.data.selectedRecord, hasPhoto: true }
            this.setData({ [`classes[${idx}].hasPhoto`]: true, selectedRecord })
            wx.showToast({ title: '上传成功', icon: 'success' })
          })
          .catch(err => {
            wx.hideLoading()
            console.error(err)
            wx.showToast({ title: '上传失败', icon: 'error' })
          })
      },
    })
  },

  async onTapTotalStudentNum() {
    _totalTapCount++
    if (_totalTapTimer) clearTimeout(_totalTapTimer)
    if (_totalTapCount < 3) {
      _totalTapTimer = setTimeout(() => { _totalTapCount = 0 }, 600)
      return
    }
    _totalTapCount = 0
    _totalTapTimer = null

    const rec = this.data.selectedRecord
    if (!rec) return

    const { dateRaw, dateIndex, apiUrl } = this.data
    const allDates = [...dateRaw].reverse()
    if (!allDates.length) {
      wx.showToast({ title: '没有历史记录', icon: 'none' })
      return
    }

    wx.showLoading({ title: '查询中...' })

    try {
      const allPrevData = await Promise.all(
        allDates.map(d => new Promise((resolve, reject) => {
          wx.request({
            url: `${apiUrl}/records`,
            method: 'GET',
            data: { date: d.date },
            success: res => resolve({ date: d.date, records: res.data }),
            fail: reject,
          })
        }))
      )
      wx.hideLoading()

      const { moduleCode, lecturer, room, totalStudentNum } = rec
      let found = null, matchLevel = 0

      const getRoomGroup = rm => {
        const parts = rm.split('-')
        if (parts.length < 2 || parts[1].length < 2) return rm
        return parts[0] + '-' + parts[1][1]
      }

      const criteria = [
        r => r.lecturer === lecturer && r.room === room && r.moduleCode === moduleCode && r.totalStudentNum === totalStudentNum && r.photoUploaded,
        r => r.lecturer === lecturer && r.room === room && r.moduleCode === moduleCode && r.photoUploaded,
        r => r.lecturer === lecturer && r.room === room && r.moduleCode !== moduleCode && r.photoUploaded,
        r => r.lecturer === lecturer && r.room !== room && getRoomGroup(r.room) === getRoomGroup(room) && r.photoUploaded,
      ]

      const allMatches = []
      const seenIds = new Set()
      for (let level = 0; level < criteria.length; level++) {
        for (const { date, records } of allPrevData) {
          records.filter(criteria[level]).forEach(record => {
            if (!seenIds.has(record.id)) {
              seenIds.add(record.id)
              const photoUrl = this._buildPhotoUrl(date, record.time, record.room)
              allMatches.push({ date, record, photoUrl, matchLevel: level + 1 })
            }
          })
        }
      }

      if (allMatches.length) {
        const first = allMatches[0]
        this.setData({
          showRefModal: true,
          refMatches: allMatches,
          refMatchIdx: 0,
          refRecord: { ...first.record, date: first.date, photoUrl: first.photoUrl },
          refMatchLevel: first.matchLevel,
        })
      } else {
        wx.showToast({ title: '未找到历史参考', icon: 'none' })
      }
    } catch (err) {
      wx.hideLoading()
      console.error(err)
      wx.showToast({ title: '查询失败', icon: 'error' })
    }
  },

  onRemarkInput(e) {
    this.setData({ inputRemark: e.detail.value })
  },

  onCancelRemark() {
    this.setData({ showRemarkModal: false, inputRemark: '' })
  },

  onHideRecord() {
    const rec = this.data.selectedRecord
    const idx = this.data.selectedIdx
    wx.showLoading({ title: '提交中...' })
    apiPatch(this.data.apiUrl, rec.id, { hidden: true })
      .then(() => {
        wx.hideLoading()
        const showHiddenItems = this.data.showHiddenItems
        const classes = this.data.classes.map((c, i) =>
          i === idx ? { ...c, hidden: true, _show: !!showHiddenItems } : c
        )
        this.setData({ classes, showRemarkModal: false, inputRemark: '' })
        wx.showToast({ title: '已隐藏', icon: 'success' })
      })
      .catch(err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '操作失败', icon: 'error' })
      })
  },

  onConfirmRemark() {
    const remark = this.data.inputRemark.trim()
    const rec = this.data.selectedRecord
    wx.showLoading({ title: '提交中...' })
    apiPatch(this.data.apiUrl, rec.id, { remark })
      .then(() => {
        wx.hideLoading()
        const idx = this.data.selectedIdx
        const classes = this.data.classes.map((c, i) => i === idx ? { ...c, remark } : c)
        const selectedRecord = { ...rec, remark }
        this.setData({ classes, selectedRecord, showRemarkModal: false, inputRemark: '' })
        wx.showToast({ title: '已更新', icon: 'success' })
      })
      .catch(err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '提交失败', icon: 'error' })
      })
  },

  _syncPhotos(classes) {
    classes.forEach((cls, idx) => {
      if (cls.hasPhoto) return
      wx.request({
        url: cls.photoUrl,
        method: 'HEAD',
        success: res => {
          if (res.statusCode !== 200) return
          const cur = this.data.classes[idx]
          if (!cur || cur.id !== cls.id) return  // 日期已切换，忽略
          this.setData({ [`classes[${idx}].hasPhoto`]: true })
          if (this.data.selectedIdx === idx) {
            this.setData({ selectedRecord: { ...this.data.selectedRecord, hasPhoto: true } })
          }
          apiPatch(this.data.apiUrl, cls.id, { photoUploaded: true })
            .then(() => console.log('[syncPhoto] DB updated, id=', cls.id))
            .catch(err => console.error('[syncPhoto] failed', err))
        },
      })
    })
  },

  onOpenEditModal() {
    const rec = this.data.selectedRecord
    this.setData({
      showRemarkModal: false,
      showEditModal: true,
      editRoom: rec.room || '',
      editDate: this.data.dateRaw[this.data.dateIndex].date,
      editTime: rec.time || '',
    })
  },

  onEditRoomInput(e) {
    this.setData({ editRoom: e.detail.value })
  },

  onEditDateInput(e) {
    this.setData({ editDate: e.detail.value })
  },

  onEditTimeInput(e) {
    this.setData({ editTime: e.detail.value })
  },

  onCancelEdit() {
    this.setData({ showEditModal: false, editRoom: '', editDate: '', editTime: '' })
  },

  onConfirmEdit() {
    const rec = this.data.selectedRecord
    const newRoom = this.data.editRoom.trim()
    const newDate = this.data.editDate.trim()
    const newTime = this.data.editTime.trim()

    const patch = {}
    if (newRoom && newRoom !== rec.room) patch.room = newRoom
    if (newDate && newDate !== this.data.dateRaw[this.data.dateIndex].date) patch.date = newDate
    if (newTime && newTime !== rec.time) patch.time = newTime

    if (!Object.keys(patch).length) {
      this.setData({ showEditModal: false, editRoom: '', editDate: '', editTime: '' })
      return
    }

    wx.showLoading({ title: '提交中...' })
    apiAttrs(this.data.apiUrl, rec.id, patch)
      .then(() => {
        wx.hideLoading()
        const idx = this.data.selectedIdx
        const room = patch.room || rec.room
        const time = patch.time || rec.time
        const date = patch.date || this.data.dateRaw[this.data.dateIndex].date
        const photoUrl = this._buildPhotoUrl(date, time, room)
        const updated = { ...rec, room, time, photoUrl }
        const classes = this.data.classes.map((c, i) => i === idx ? { ...c, room, time, photoUrl } : c)
        this.setData({
          classes,
          selectedRecord: updated,
          showEditModal: false,
          editRoom: '',
          editDate: '',
          editTime: '',
        })
        wx.showToast({ title: '已更新', icon: 'success' })
        if (patch.date) this.onQuery()
      })
      .catch(err => {
        wx.hideLoading()
        console.error(err)
        wx.showToast({ title: '提交失败', icon: 'error' })
      })
  },

  onTapNickname() {
    if (_nickTapTimer) {
      clearTimeout(_nickTapTimer)
      _nickTapTimer = null
      this.onQuery()
      wx.showToast({ title: '刷新中', icon: 'loading', duration: 1000 })
      return
    }
    _nickTapTimer = setTimeout(() => {
      _nickTapTimer = null
      this.setData({ showVisibilityModal: true })
    }, 300)
  },

  onReLogin() {
    this.setData({ showVisibilityModal: false, showLoginModal: true, inputName: '' })
  },

  onCloseVisibilityModal() {
    this.setData({ showVisibilityModal: false })
  },

  onToggleShowHidden(e) {
    const showHiddenItems = e.detail.value
    const classes = this.data.classes.map(c => ({
      ...c,
      _show: !c.hidden || showHiddenItems,
    }))
    this.setData({ showHiddenItems, classes })
  },

  onSyncFromRef() {
    this.setData({
      showRefModal: false,
      showInputModal: true,
      inputCount: '',
      syncFromRef: true,
      refHistoricalCount: this.data.refRecord.studentNumInClassroom,
    })
  },

  onRefPrev() {
    const { refMatches, refMatchIdx } = this.data
    const idx = (refMatchIdx - 1 + refMatches.length) % refMatches.length
    const m = refMatches[idx]
    this.setData({ refMatchIdx: idx, refRecord: { ...m.record, date: m.date, photoUrl: m.photoUrl }, refMatchLevel: m.matchLevel })
  },

  onRefNext() {
    const { refMatches, refMatchIdx } = this.data
    const idx = (refMatchIdx + 1) % refMatches.length
    const m = refMatches[idx]
    this.setData({ refMatchIdx: idx, refRecord: { ...m.record, date: m.date, photoUrl: m.photoUrl }, refMatchLevel: m.matchLevel })
  },

  onCloseRefModal() {
    this.setData({ showRefModal: false, refRecord: null, refMatches: [], refMatchIdx: 0, refMatchLevel: 0 })
  },

  noop() {},
})
