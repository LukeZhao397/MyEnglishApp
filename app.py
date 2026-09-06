import streamlit as st
import json
from datetime import datetime, timedelta
from github import Github
from gtts import gTTS
import io

# ================= 1. 初始化与配置 =================
st.set_page_config(page_title="英语碎片学", layout="centered")

# 从 Streamlit Secrets 中读取配置
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
DATA_REPO_NAME = "LukeZhao397/MyEnglishData" # 这里填入你真实的数据仓库路径
DATA_FILE_PATH = "words_progress.json"
DAILY_GOAL = 10

# ================= 2. 核心功能函数 =================
@st.cache_resource
def get_repo():
    g = Github(GITHUB_TOKEN)
    return g.get_repo(DATA_REPO_NAME)

def load_data():
    repo = get_repo()
    file_content = repo.get_contents(DATA_FILE_PATH)
    data = json.loads(file_content.decoded_content.decode('utf-8'))
    return data, file_content.sha

def save_data(data, sha):
    repo = get_repo()
    new_content = json.dumps(data, ensure_ascii=False, indent=2)
    repo.update_file(DATA_FILE_PATH, f"Update progress {datetime.now().strftime('%Y-%m-%d')}", new_content, sha)

def play_audio(text):
    # 动态生成标准发音音频
    tts = gTTS(text=text, lang='en', tld='us') # 美音
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    st.audio(fp, format='audio/mp3', autoplay=True)

# ================= 3. 会话状态管理 =================
if 'db' not in st.session_state:
    st.session_state.db, st.session_state.file_sha = load_data()
    
    # 筛选出今天需要学习/复习的单词 (最多取10个)
    today_str = datetime.now().strftime("%Y-%m-%d")
    pending_words = [k for k, v in st.session_state.db.items() if v["next_review"] <= today_str]
    st.session_state.today_queue = pending_words[:DAILY_GOAL]
    st.session_state.completed_today = 0
    st.session_state.show_back = False

# ================= 4. UI与交互主逻辑 =================
if st.session_state.completed_today >= len(st.session_state.today_queue) and len(st.session_state.today_queue) > 0:
    st.balloons()
    st.success("🎉 你真棒！今天学习了 {} 个单词，比昨天又进步了一点点！".format(st.session_state.completed_today))
    
    # 统计面板
    total_words = len(st.session_state.db)
    learned_words = len([v for v in st.session_state.db.values() if v["interval"] > 0])
    progress = int((learned_words / total_words) * 100)
    
    st.progress(progress / 100.0)
    st.write(f"📊 小学词汇完成进度：**{progress}%** ({learned_words}/{total_words})")
    
    if st.button("同步进度到云端"):
        with st.spinner("正在保存进度..."):
            save_data(st.session_state.db, st.session_state.file_sha)
        st.success("进度保存成功！明天见~")
        
elif len(st.session_state.today_queue) == 0:
    st.info("今天没有需要学习或复习的单词啦，休息一下吧！")
else:
    # 取出当前要学习的单词
    current_word_key = st.session_state.today_queue[st.session_state.completed_today]
    word_info = st.session_state.db[current_word_key]
    
    # 进度提示
    st.caption(f"今日进度: {st.session_state.completed_today + 1} / {len(st.session_state.today_queue)}")
    
    # 正面展示
    st.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{word_info['word']}</h1>", unsafe_allow_html=True)
    
    if not st.session_state.show_back:
        # 点击看背面
        play_audio(word_info['word'])
        if st.button("点击查看解析 💡", use_container_width=True):
            st.session_state.show_back = True
            st.rerun()
    else:
        # 背面展示
        st.divider()
        st.markdown(f"<h3 style='text-align: center; color: gray;'>{word_info['phonetic']} | {word_info['phonics_chunk']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align: center;'>{word_info['meaning']}</h2>", unsafe_allow_html=True)
        st.caption(f"🏷️ 标签: {word_info.get('remark', '')}")
        
        st.markdown("#### 📖 简单例句：")
        for sentence in word_info['sentence']:
            st.write(f"- {sentence}")
        
        st.divider()
        
        # 计分算法调度函数
        def handle_click(quality):
            interval = word_info["interval"]
            if quality == "hard": # 不认识
                new_interval = 0
            elif quality == "good": # 不熟
                new_interval = 1
            else: # 认识
                new_interval = interval * 2 if interval > 0 else 1
            
            # 计算下次复习日期
            next_date = datetime.now() + timedelta(days=new_interval)
            
            # 更新状态
            st.session_state.db[current_word_key]["interval"] = new_interval
            st.session_state.db[current_word_key]["next_review"] = next_date.strftime("%Y-%m-%d")
            st.session_state.db[current_word_key]["learned_count"] += 1
            
            # 切换下一个单词
            st.session_state.completed_today += 1
            st.session_state.show_back = False
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.button("🔴 不认识", on_click=handle_click, args=("hard",), use_container_width=True)
        with col2:
            st.button("🟡 不熟", on_click=handle_click, args=("good",), use_container_width=True)
        with col3:
            st.button("🟢 认识", on_click=handle_click, args=("easy",), use_container_width=True)
