import io, json, math, random
from copy import deepcopy
from datetime import datetime, timedelta, timezone, date
from zoneinfo import ZoneInfo

import streamlit as st
from github import Github
from gtts import gTTS
from fsrs import Scheduler, Card, Rating, State

APP_VERSION = "2.0.0"
DATA_REPO_NAME = "LukeZhao397/MyEnglishData"
DATA_FILE_PATH = "words_progress.json"
DAILY_NEW_WORDS = 8
DAILY_REVIEW_LIMIT = 22
DAILY_MAX_CARDS = 30
DESIRED_RETENTION = 0.90
AUTO_SAVE_EVERY = 5
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

st.set_page_config(page_title="🌳 小小词汇树", page_icon="🌳", layout="centered")

st.markdown("""
<style>
.stApp{background:linear-gradient(180deg,#f8fbf7 0%,#fff 55%,#f7faf7 100%)}
.block-container{max-width:860px;padding-top:1rem;padding-bottom:4rem}
.title-main{text-align:center;font-size:2.2rem;font-weight:800;margin-bottom:.2rem}
.subtitle{text-align:center;color:#6b7280;font-size:1rem;margin-bottom:1rem}
.metric-card{border:1px solid #e5e7eb;border-radius:18px;padding:16px 12px;background:#fff;box-shadow:0 4px 16px rgba(0,0,0,.04);text-align:center;min-height:100px}
.metric-number{font-size:1.65rem;font-weight:800;margin-top:4px}.metric-label{color:#6b7280;font-size:.9rem}
.streak{border-radius:16px;padding:12px 18px;background:linear-gradient(90deg,#fff7ed,#fff1df);border:1px solid #fed7aa;text-align:center;font-size:1.05rem;font-weight:700;margin:8px 0 18px}
.xp-box{border-radius:16px;padding:10px 16px;background:linear-gradient(90deg,#eff6ff,#eefdf5);border:1px solid #dbeafe;text-align:center;margin-bottom:14px}
.word-card{background:#fff;border-radius:26px;padding:42px 24px 32px;border:1px solid #e5e7eb;box-shadow:0 12px 35px rgba(0,0,0,.06);text-align:center;margin:18px 0}
.word{font-size:clamp(3.4rem,12vw,6.8rem);line-height:1.05;font-weight:900;letter-spacing:-.02em;margin:10px 0 14px;word-break:break-word}
.phonetic{color:#6b7280;font-size:clamp(1.15rem,3vw,1.6rem);margin-bottom:8px}.meaning{font-size:clamp(1.6rem,4vw,2.1rem);font-weight:800;margin:10px 0 16px}
.tag{display:inline-block;border-radius:999px;background:#f3f4f6;color:#6b7280;padding:5px 12px;font-size:.85rem}
.example-box{text-align:left;border-radius:16px;background:#f8fafc;border:1px solid #e5e7eb;padding:14px 16px;margin:10px 0}
.example-en{font-size:1.08rem;line-height:1.5;font-weight:600}.tiny-hint{color:#6b7280;font-size:.9rem}
.heatmap-wrap{overflow-x:auto;padding-bottom:6px}.heatmap{display:grid;grid-auto-flow:column;grid-template-rows:repeat(7,16px);grid-auto-columns:16px;gap:4px;width:max-content;padding:8px}
.heat{width:16px;height:16px;border-radius:4px;border:1px solid rgba(0,0,0,.04)}
.heat-0{background:#eef2ee}.heat-1{background:#d8f3dc}.heat-2{background:#95d5b2}.heat-3{background:#52b788}.heat-4{background:#2d6a4f}
.badge{display:inline-block;padding:7px 11px;border-radius:999px;background:#fef3c7;margin:3px;font-weight:700;font-size:.85rem}
div.stButton>button{min-height:50px;border-radius:14px;font-size:1.04rem;font-weight:700}
.footer-note{color:#9ca3af;text-align:center;font-size:.8rem;margin-top:28px}
</style>
""", unsafe_allow_html=True)

def now_local(): return datetime.now(LOCAL_TZ)
def today_str(): return now_local().strftime("%Y-%m-%d")
def utc_now(): return datetime.now(timezone.utc)

@st.cache_resource
def get_repo():
    return Github(st.secrets["GITHUB_TOKEN"]).get_repo(DATA_REPO_NAME)

def load_remote_data():
    f = get_repo().get_contents(DATA_FILE_PATH)
    return json.loads(f.decoded_content.decode("utf-8")), f.sha

def save_remote_data(data, sha):
    content = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        r = get_repo().update_file(DATA_FILE_PATH, f"V2 progress {today_str()}", content, sha)
    except Exception:
        latest = get_repo().get_contents(DATA_FILE_PATH)
        r = get_repo().update_file(DATA_FILE_PATH, f"V2 progress {today_str()}", content, latest.sha)
    return r["content"].sha

def default_meta():
    return {"schema_version":2,"app_version":APP_VERSION,"created_at":now_local().isoformat(),
            "xp":0,"total_reviews":0,"study_days":[],"daily_stats":{},"badges":[],
            "current_streak":0,"best_streak":0,"last_study_date":None,
            "monthly_protection":2,"protection_used":0}

def is_word_entry(v):
    return isinstance(v,dict) and "word" in v and "meaning" in v

def migrate_data(raw):
    if isinstance(raw,dict) and "words" in raw and "_meta" in raw:
        data = raw
    else:
        data = {"_meta":default_meta(),"words":{}}
        for k,v in raw.items():
            if is_word_entry(v): data["words"][k] = v
    meta=data.setdefault("_meta",default_meta())
    for k,v in default_meta().items(): meta.setdefault(k,v)
    for w in data["words"].values():
        w.setdefault("interval",0); w.setdefault("next_review",today_str()); w.setdefault("learned_count",0)
        w.setdefault("review_history",[]); w.setdefault("fsrs_card",None); w.setdefault("last_rating",None)
        w.setdefault("updated_at",None); w.setdefault("image_url",""); w.setdefault("part_of_speech","")
        w.setdefault("source",w.get("remark","")); w.setdefault("phonetic_us",w.get("phonetic",""))
        w.setdefault("examples_audio",[]); w.setdefault("sentence",[])
    meta["schema_version"]=2; meta["app_version"]=APP_VERSION
    return data

def ensure_fsrs_card(word_info):
    if word_info.get("fsrs_card"):
        try: return Card.from_json(word_info["fsrs_card"])
        except Exception: pass
    card=Card()
    learned=int(word_info.get("learned_count",0) or 0); interval=int(word_info.get("interval",0) or 0)
    if learned>0 and interval>0:
        try:
            card.state=State.Review; card.step=None; card.stability=max(1.,float(interval)); card.difficulty=5.
            due=datetime.strptime(word_info.get("next_review",today_str()),"%Y-%m-%d").replace(tzinfo=LOCAL_TZ)
            card.due=due.astimezone(timezone.utc); card.last_review=(due-timedelta(days=max(1,interval))).astimezone(timezone.utc)
        except Exception: pass
    return card

def serialize_card(card): return card.to_json()

@st.cache_resource
def get_scheduler():
    return Scheduler(desired_retention=DESIRED_RETENTION,enable_fuzzing=True,maximum_interval=36500)

def due_keys(data):
    t=today_str(); return [k for k,w in data["words"].items() if str(w.get("next_review",t))<=t]

def new_keys(data):
    return [k for k,w in data["words"].items() if int(w.get("learned_count",0) or 0)==0]

def choose_queue(data):
    due=due_keys(data); new=new_keys(data); random.shuffle(due); random.shuffle(new)
    return list(dict.fromkeys(due[:DAILY_REVIEW_LIMIT]+new[:DAILY_NEW_WORDS]))[:DAILY_MAX_CARDS]

def stats(data):
    ws=data["words"]; total=len(ws)
    learned=sum(int(w.get("learned_count",0) or 0)>0 for w in ws.values())
    stable=sum(float(w.get("stability",0) or 0)>=21 for w in ws.values())
    return total,learned,stable,len(due_keys(data)),len(new_keys(data))

def record_daily(data,was_new,xp):
    m=data["_meta"]; t=today_str(); s=m["daily_stats"].setdefault(t,{"reviews":0,"new_words":0,"xp":0,"minutes":0})
    s["reviews"]+=1; s["new_words"]+=int(was_new); s["xp"]+=xp; m["total_reviews"]+=1; m["xp"]+=xp
    if t not in m["study_days"]: m["study_days"].append(t)

def update_streak(data):
    m=data["_meta"]; t=today_str()
    if m.get("last_study_date")==t: return
    last=m.get("last_study_date")
    if not last: m["current_streak"]=1
    else:
        diff=(date.fromisoformat(t)-date.fromisoformat(last)).days
        if diff==1: m["current_streak"]+=1
        elif diff>1 and m.get("protection_used",0)<m.get("monthly_protection",0):
            m["protection_used"]+=1
        else: m["current_streak"]=1
    m["best_streak"]=max(m.get("best_streak",0),m["current_streak"]); m["last_study_date"]=t
    if t not in m["study_days"]: m["study_days"].append(t)

def badges(data):
    m=data["_meta"]; b=set(m.get("badges",[])); st=m.get("current_streak",0); xp=m.get("xp",0); r=m.get("total_reviews",0)
    for n,label in [(7,"🔥 7天连胜"),(30,"🔥 30天连胜"),(100,"🔥 100天连胜")]:
        if st>=n:b.add(label)
    for n,label in [(100,"⭐ 100 XP"),(1000,"🏆 1000 XP")]:
        if xp>=n:b.add(label)
    for n,label in [(100,"📚 100次复习"),(500,"📚 500次复习")]:
        if r>=n:b.add(label)
    m["badges"]=sorted(b)

@st.cache_data(ttl=86400,show_spinner=False)
def make_audio(text):
    fp=io.BytesIO(); gTTS(text=text,lang="en",tld="us").write_to_fp(fp); return fp.getvalue()

def audio(text):
    try: st.audio(make_audio(text),format="audio/mp3")
    except Exception: st.caption("🔊 当前网络无法生成朗读音频，请稍后再试。")

def metric(label,value):
    return f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-number">{value}</div></div>'

def heatmap(data,days=84):
    end=now_local().date(); start=end-timedelta(days=days-1); counts={}
    for d,s in data["_meta"].get("daily_stats",{}).items(): counts[d]=int(s.get("reviews",0))
    cells=[]; cur=start
    while cur<=end:
        c=counts.get(cur.strftime("%Y-%m-%d"),0); lvl=4 if c>=20 else 3 if c>=10 else 2 if c>=4 else 1 if c else 0
        cells.append(f'<div class="heat heat-{lvl}" title="{cur}: {c}次复习"></div>'); cur+=timedelta(days=1)
    st.markdown('<div class="heatmap-wrap"><div class="heatmap">'+''.join(cells)+'</div></div>',unsafe_allow_html=True)

if "db" not in st.session_state:
    raw,sha=load_remote_data(); st.session_state.db=migrate_data(raw); st.session_state.file_sha=sha
    st.session_state.queue=choose_queue(st.session_state.db); st.session_state.index=0
    st.session_state.show_back=False; st.session_state.session_reviews=0; st.session_state.session_xp=0
    st.session_state.last_saved_reviews=0; st.session_state.session_started_at=utc_now()

db=st.session_state.db
page=st.radio("",["🌱 今日学习","📊 我的成长","🎒 词库"],horizontal=True,label_visibility="collapsed")
st.divider()

if page=="🌱 今日学习":
    total,learned,stable,due,new_count=stats(db); m=db["_meta"]
    st.markdown('<div class="title-main">🌳 小小词汇树</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{today_str()} · 每天一点点，词汇树慢慢长大</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="streak">🔥 连续学习 {m.get("current_streak",0)} 天 · 历史最佳 {m.get("best_streak",0)} 天</div>',unsafe_allow_html=True)
    st.progress(min(1,learned/total) if total else 0,text=f"词汇树成长 {learned}/{total} · {learned/total*100:.0f}%" if total else "词汇树成长 0/0")
    a,b,c,d=st.columns(4)
    for col,label,val in [(a,"今日待复习",due),(b,"新词池",new_count),(c,"本次 XP",st.session_state.session_xp),(d,"累计 XP",m.get("xp",0))]:
        with col: st.markdown(metric(label,val),unsafe_allow_html=True)
    queue=st.session_state.queue
    if len(queue)==0:
        st.success("🎉 今天没有必须复习的单词了。可以休息，也可以主动学习几个新词。")
        if st.button("🌟 随机学 5 个词",use_container_width=True):
            q=list(db["words"]); random.shuffle(q); st.session_state.queue=q[:5]; st.session_state.index=0; st.rerun()
    elif st.session_state.index>=len(queue):
        update_streak(db); badges(db); st.balloons()
        mins=max(1,round((utc_now()-st.session_state.session_started_at).total_seconds()/60))
        s=db["_meta"]["daily_stats"].setdefault(today_str(),{"reviews":0,"new_words":0,"xp":0,"minutes":0}); s["minutes"]=max(s.get("minutes",0),mins)
        st.markdown(f'<div class="word-card"><div style="font-size:4rem;">🎉</div><h2>今天完成啦！</h2><p style="font-size:1.15rem;">完成 {st.session_state.session_reviews} 次复习</p><p style="font-size:1.15rem;">获得 ⭐ {st.session_state.session_xp} XP</p><p style="font-size:1.15rem;">🔥 连续学习 {db["_meta"].get("current_streak",1)} 天</p></div>',unsafe_allow_html=True)
        if m.get("current_streak",0) in {7,14,30,50,100}: st.info(f"🎁 隐藏彩蛋：恭喜你完成 {m.get('current_streak')} 天连续学习！今天的小树偷偷长高了一截。")
        try:
            st.session_state.file_sha=save_remote_data(db,st.session_state.file_sha); st.success("☁️ 学习进度已自动同步到 GitHub")
        except Exception as e: st.warning(f"云端同步失败：{e}")
        if st.button("🔄 再来一次",use_container_width=True):
            st.session_state.queue=choose_queue(db); st.session_state.index=0; st.session_state.show_back=False
            st.session_state.session_reviews=0; st.session_state.session_xp=0; st.session_state.session_started_at=utc_now(); st.rerun()
    else:
        key=queue[st.session_state.index]; w=db["words"][key]
        st.progress(st.session_state.index/len(queue),text=f"今日进度 {st.session_state.index+1}/{len(queue)}")
        word=w.get("word",key); meaning=w.get("meaning",""); phon=w.get("phonetic_us") or w.get("phonetic","")
        st.markdown('<div class="word-card">',unsafe_allow_html=True)
        st.markdown(f'<div class="word">{word}</div><div class="phonetic">{phon}</div>',unsafe_allow_html=True)
        if w.get("phonics_chunk"): st.caption(f'🧩 {w["phonics_chunk"]}')
        if not st.session_state.show_back:
            audio(word); st.markdown('<div class="tiny-hint">先想一想：这个词是什么意思？</div>',unsafe_allow_html=True)
            if st.button("💡 点击看看意思",use_container_width=True): st.session_state.show_back=True; st.rerun()
        else:
            st.markdown(f'<div class="meaning">{meaning}</div>',unsafe_allow_html=True)
            if w.get("remark"): st.markdown(f'<span class="tag">🏷️ {w["remark"]}</span>',unsafe_allow_html=True)
            audio(word)
            if w.get("image_url"): st.image(w["image_url"],use_container_width=True)
            if w.get("sentence"):
                st.markdown("### 📖 生活里的例句")
                for i,s in enumerate(w["sentence"][:3],1):
                    st.markdown(f'<div class="example-box"><div class="example-en">{i}. {s}</div></div>',unsafe_allow_html=True); audio(s)
            if word.lower() in {"borrow","lend"}: st.info("💡 borrow 是“借进来”，lend 是“借出去”。")
            elif word.lower() in {"book","change","free","notice"}: st.info("💡 这个词有不止一个常见意思，阅读中要结合上下文。")
        st.markdown("</div>",unsafe_allow_html=True)
        if st.session_state.show_back:
            st.markdown("### 我刚才记得怎么样？")
            cols=st.columns(4)
            ratings=[("忘了","again"),("很模糊","hard"),("记得","good"),("很熟","easy")]
            for col,(label,rname) in zip(cols,ratings):
                with col:
                    if st.button(("🔴 " if rname=="again" else "🟠 " if rname=="hard" else "🟢 " if rname=="good" else "⭐ ")+label,use_container_width=True):
                        scheduler=get_scheduler(); old=deepcopy(db["words"][key]); card=ensure_fsrs_card(old)
                        new_card,log=scheduler.review_card(card,{"again":Rating.Again,"hard":Rating.Hard,"good":Rating.Good,"easy":Rating.Easy}[rname],review_datetime=utc_now())
                        was_new=int(old.get("learned_count",0) or 0)==0; gain={"again":1,"hard":2,"good":3,"easy":4}[rname]; entry=db["words"][key]
                        entry["fsrs_card"]=serialize_card(new_card); entry["fsrs_state"]=new_card.state.name
                        entry["stability"]=float(new_card.stability or 0); entry["difficulty"]=float(new_card.difficulty or 0)
                        entry["next_review"]=new_card.due.astimezone(LOCAL_TZ).strftime("%Y-%m-%d"); entry["learned_count"]=int(entry.get("learned_count",0) or 0)+1
                        entry["last_rating"]=rname; entry["updated_at"]=now_local().isoformat()
                        h=entry.setdefault("review_history",[]); h.append({"date":today_str(),"rating":rname,"next_review":entry["next_review"]}); entry["review_history"]=h[-100:]
                        record_daily(db,was_new,gain); update_streak(db); badges(db)
                        st.session_state.session_reviews+=1; st.session_state.session_xp+=gain
                        if st.session_state.session_reviews-st.session_state.last_saved_reviews>=AUTO_SAVE_EVERY:
                            try:
                                st.session_state.file_sha=save_remote_data(db,st.session_state.file_sha); st.session_state.last_saved_reviews=st.session_state.session_reviews; st.toast("☁️ 进度已同步")
                            except Exception: st.toast("☁️ 云端同步暂时失败")
                        st.session_state.index+=1; st.session_state.show_back=False; st.rerun()
        st.markdown(f'<div class="xp-box">本次学习已获得 ⭐ {st.session_state.session_xp} XP</div>',unsafe_allow_html=True)

elif page=="📊 我的成长":
    total,learned,stable,due,new_count=stats(db); m=db["_meta"]
    st.markdown('<div class="title-main">📊 我的成长</div>',unsafe_allow_html=True)
    st.progress(min(1,learned/total) if total else 0,text=f"已认识 {learned}/{total} · {learned/total*100:.0f}%" if total else "已认识 0/0")
    a,b,c=st.columns(3)
    for col,label,val in [(a,"已接触词汇",learned),(b,"累计复习",m.get("total_reviews",0)),(c,"累计 XP",m.get("xp",0))]:
        with col: st.markdown(metric(label,val),unsafe_allow_html=True)
    st.markdown("### 🔥 我的连胜"); st.success(f'连续学习 {m.get("current_streak",0)} 天 · 历史最佳 {m.get("best_streak",0)} 天')
    st.markdown("### 📅 我的英语足迹"); heatmap(db)
    st.markdown("### 🏅 已获得徽章")
    bs=m.get("badges",[])
    st.markdown("".join(f'<span class="badge">{x}</span>' for x in bs) if bs else "还没有徽章，坚持几天就会有第一枚啦！",unsafe_allow_html=True)
    st.markdown("### 🧠 最近的薄弱词")
    weak=[w for w in db["words"].values() if w.get("last_rating") in {"again","hard"}]
    for w in weak[:10]: st.write(f'• **{w.get("word","")}** — {w.get("meaning","")} · 最近：{w.get("last_rating","")}')
    if not weak: st.success("目前没有明显薄弱词 👍")
    st.markdown("### 📚 词库覆盖")
    src={}
    for w in db["words"].values():
        s=w.get("source") or w.get("remark") or "未分类"; src[s]=src.get(s,0)+1
    for s,n in sorted(src.items(),key=lambda x:x[1],reverse=True): st.write(f"**{s}**：{n} 词")

else:
    st.markdown('<div class="title-main">🎒 我的词库</div>',unsafe_allow_html=True)
    st.info("以后可以继续把小学、KET、初中、高中词库加入这里；V2.0 会尽量保留已有学习记录。")
    q=st.text_input("🔎 搜索单词",placeholder="例如 important")
    options=sorted({w.get("source") or w.get("remark") or "未分类" for w in db["words"].values()})
    sf=st.selectbox("词库来源",["全部"]+options)
    items=[]
    for k,w in db["words"].items():
        text=f'{w.get("word","")} {w.get("meaning","")} {w.get("remark","")}'.lower()
        source=w.get("source") or w.get("remark") or "未分类"
        if q and q.lower() not in text: continue
        if sf!="全部" and sf!=source: continue
        items.append((k,w))
    st.caption(f"找到 {len(items)} 个词")
    for k,w in items[:100]:
        with st.expander(f'{w.get("word",k)} · {w.get("meaning","")}'):
            st.write(f'音标：{w.get("phonetic_us") or w.get("phonetic","")}')
            st.write(f'分音：{w.get("phonics_chunk","")}')
            st.write(f'标签：{w.get("remark","")}')
            st.write(f'学习次数：{w.get("learned_count",0)} · 下次复习：{w.get("next_review",today_str())}')
            for s in w.get("sentence",[])[:3]: st.write(f"• {s}")

st.markdown(f'<div class="footer-note">小小词汇树 V{APP_VERSION} · 每天一点点，几年后会有很大的不同 🌱</div>',unsafe_allow_html=True)
