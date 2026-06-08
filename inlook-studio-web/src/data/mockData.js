export const navigationItems = [
  { id: 'home', label: '首页', icon: '⌂' },
  { id: 'material', label: '素材', icon: '◫' },
  { id: 'script', label: '文案', icon: '✎' },
  { id: 'voice', label: '配音', icon: '◌' },
  { id: 'human', label: '数字人', icon: '◍' },
  { id: 'edit', label: '剪辑', icon: '⎇' },
  { id: 'export', label: '导出', icon: '⇪' },
  { id: 'tasks', label: '任务', icon: '☷' },
  { id: 'settings', label: '设置', icon: '⚙' },
]

export const promptTemplates = [
  '爆款开头',
  '普通人分享',
  '知识讲解',
  '小红书种草',
  '私域引流',
  '老板口播',
  '课程转化',
  '避坑提醒',
]

export const platformOptions = ['抖音', '视频号', '小红书', 'B站']
export const lengthOptions = ['150字', '300字', '500字', '自定义']
export const toneOptions = ['真实自然', '直接', '温和', '专业', '接地气']
export const emotionOptions = ['真诚自然', '轻松分享', '专业讲解', '克制表达']
export const subtitleStyles = ['简约白底黑字', '灰底圆角字幕', '专业知识字幕']
export const subtitlePositions = ['底部居中', '底部偏上', '上方标题位']
export const bgmOptions = ['轻节奏 Lo-fi', '清爽讲解氛围', '商务感轻电子']
export const aspectOptions = ['9:16', '16:9', '1:1']
export const qualityOptions = ['720P', '1080P']

export const avatarOptions = [
  {
    id: 'elite-01',
    name: '精英职场-01',
    role: '偏商务表达',
    accent: 'linear-gradient(160deg, #4a5566, #272b33)',
  },
  {
    id: 'grace-02',
    name: '知性女神-02',
    role: '偏温和分享',
    accent: 'linear-gradient(160deg, #5a4d53, #2b2d30)',
  },
  {
    id: 'business-03',
    name: '商务男声-03',
    role: '偏课程讲解',
    accent: 'linear-gradient(160deg, #445365, #23262b)',
  },
]

export const sceneOptions = ['半身', '胸像', '全身']
export const backgroundOptions = ['现代办公室', '纯色深灰背景', '暖光书房']

export const initialRawScript = `今天想跟大家聊一个很多人做口播时都会遇到的问题：为什么明明内容不差，讲出来却没有那种自然、有说服力的感觉？大多数时候，不是你不会讲，而是文案太像“写出来的”，不像“说出来的”。如果你想让内容更像真实分享，第一步要先把表达里的书面腔拿掉。`

export const initialRewriteResults = [
  {
    id: 'A',
    title: '版本 A',
    tag: '真实口播版',
    content:
      '很多人做口播时总觉得自己内容没问题，但一开口就是不自然。问题通常不在你不会讲，而在文案太书面。想让观众更愿意听下去，先别急着堆观点，先把语气改得像你真的在和一个朋友聊天。',
  },
  {
    id: 'B',
    title: '版本 B',
    tag: '爆款钩子版',
    content:
      '为什么有的人口播一开头就能把人留住，而你的内容三秒就划走？不是你内容差，是你一上来就像在背稿。真正有效的口播，第一句话就得让人觉得“这人像在说我”。',
  },
  {
    id: 'C',
    title: '版本 C',
    tag: '专业讲解版',
    content:
      '如果口播内容缺少自然度，往往说明文案仍然停留在书面表达阶段。更适合短视频的写法，应该优先口语化、情境化，并在开头建立明确的问题感，这样更容易形成停留和听完率。',
  },
]

export const initialTasks = [
  {
    id: 'task-1',
    name: '职场表达优化分享',
    source: '本地视频',
    step: '已完成',
    status: '已完成',
    createdAt: '2026-06-04 19:20',
    progress: 100,
  },
  {
    id: 'task-2',
    name: '课程转化口播测试',
    source: '手动输入',
    step: '配音生成',
    status: '进行中',
    createdAt: '2026-06-04 18:47',
    progress: 58,
  },
  {
    id: 'task-3',
    name: '私域引流脚本重写',
    source: '视频链接',
    step: '改写完成',
    status: '等待中',
    createdAt: '2026-06-04 17:35',
    progress: 24,
  },
]
