# 小小词汇树 V2.0

基于原有 Streamlit + GitHub + words_progress.json 升级。

## 已实现
- iPad 友好的大字体学习卡片
- 正面/背面学习
- 美式朗读
- 三条例句朗读
- 4档记忆评价
- FSRS 间隔重复
- 自动 GitHub 同步
- 兼容旧版 words_progress.json
- 今日任务：复习 + 新词
- XP、连胜、徽章
- 84 天学习热力图
- 成长统计、薄弱词
- 词库搜索和来源筛选

## 部署
1. 用 app.py 替换原主程序。
2. 用 requirements.txt 替换依赖。
3. Streamlit Secrets 中保留：
   GITHUB_TOKEN="你的 GitHub Token"
4. 数据仓库继续使用：
   LukeZhao397/MyEnglishData
5. 数据文件继续使用：
   words_progress.json

首次运行会自动把 V0.1 数据包装成 V2 结构。建议先备份现有 JSON。

## 说明
旧版没有完整的复习历史，因此第一次切到 FSRS 时只能根据原 interval 做温和迁移；从 V2 开始的新复习会由 FSRS 管理。
