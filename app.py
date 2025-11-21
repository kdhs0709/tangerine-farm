import streamlit as st
import pandas as pd
import uuid
import io
import os
from datetime import datetime

# =============================================================================
# 📱 [설정] 페이지 및 디자인 (모바일 초밀착 모드)
# =============================================================================
st.set_page_config(
    page_title="감귤 농장 Manager",
    page_icon="🍊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
    /* 전체 여백 최소화 */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    /* 버튼 스타일 */
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3.5em;
        font-weight: bold;
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* 표 헤더 글씨 크기 조정 */
    th {
        font-size: 14px !important;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 💾 [데이터베이스]
# =============================================================================
DB_FILE = "customer_db.csv"
HISTORY_FILE = "order_history.csv"
CONFIG_FILE = "config.csv"

def init_state():
    if 'df' not in st.session_state:
        if os.path.exists(DB_FILE):
            try:
                df = pd.read_csv(DB_FILE, dtype=str)
                if 'ordered' in df.columns:
                    df['ordered'] = df['ordered'].apply(lambda x: str(x).lower() == 'true')
                else: df['ordered'] = False
                if 'qty' in df.columns:
                    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').fillna(0).astype(int)
                else: df['qty'] = 0
                for col in ['sender_name', 'sender_phone', 'sender_addr']:
                    if col not in df.columns: df[col] = ""
                
                df = df.sort_values(by='name').reset_index(drop=True)
                st.session_state.df = df
            except:
                st.session_state.df = pd.DataFrame(columns=["id", "ordered", "name", "phone", "address", "qty", "memo", "sender_name", "sender_phone", "sender_addr"])
        else:
            st.session_state.df = pd.DataFrame(columns=["id", "ordered", "name", "phone", "address", "qty", "memo", "sender_name", "sender_phone", "sender_addr"])

    if 'history' not in st.session_state:
        if os.path.exists(HISTORY_FILE):
            try: st.session_state.history = pd.read_csv(HISTORY_FILE)
            except: st.session_state.history = pd.DataFrame(columns=["date", "name", "phone", "qty"])
        else:
            st.session_state.history = pd.DataFrame(columns=["date", "name", "phone", "qty"])

    if 'sender' not in st.session_state:
        if os.path.exists(CONFIG_FILE):
            try: st.session_state.sender = pd.read_csv(CONFIG_FILE).iloc[0].to_dict()
            except: st.session_state.sender = {"name": "", "phone": "", "addr": ""}
        else:
            st.session_state.sender = {"name": "제주감귤농장", "phone": "010-0000-0000", "addr": "제주도"}

def save_all():
    st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
    st.session_state.df.to_csv(DB_FILE, index=False)
    st.session_state.history.to_csv(HISTORY_FILE, index=False)
    pd.DataFrame([st.session_state.sender]).to_csv(CONFIG_FILE, index=False)

init_state()

# =============================================================================
# 🧠 [Logic] 스마트 엑셀 로더
# =============================================================================
def smart_import_ai(file):
    try:
        df_raw = pd.read_excel(file, header=None)
        keywords = {
            "name": ["이름", "성함", "고객명", "받는분"],
            "phone": ["전화", "연락처", "H.P", "Mobile"],
            "address": ["주소", "배송지"],
            "qty": ["수량", "박스", "개수"],
            "memo": ["비고", "메모"]
        }
        best_header_row = -1
        max_matches = 0
        column_indices = {}
        scan_limit = min(20, len(df_raw))
        
        for i in range(scan_limit):
            row_values = df_raw.iloc[i].astype(str).tolist()
            current_matches = 0
            current_mapping = {}
            for col_idx, cell_value in enumerate(row_values):
                clean_val = cell_value.replace(" ", "").replace("\n", "").lower()
                if clean_val == "nan": continue
                for key, synonyms in keywords.items():
                    if key in current_mapping: continue
                    for s in synonyms:
                        if s in clean_val:
                            current_mapping[key] = col_idx
                            current_matches += 1
                            break
            if current_matches > max_matches and ('name' in current_mapping or 'phone' in current_mapping):
                max_matches = current_matches
                best_header_row = i
                column_indices = current_mapping

        if best_header_row == -1: return None, "데이터 시작 위치를 찾지 못했습니다."

        extracted_data = []
        for i in range(best_header_row + 1, len(df_raw)):
            row = df_raw.iloc[i]
            try:
                raw_name = str(row[column_indices["name"]])
                if raw_name == "nan" or raw_name.strip() == "": continue
                name = raw_name.strip()
            except: continue

            phone = str(row[column_indices["phone"]]).strip() if "phone" in column_indices else ""
            if phone == "nan": phone = ""
            address = str(row[column_indices["address"]]).strip() if "address" in column_indices else ""
            if address == "nan": address = ""
            memo = str(row[column_indices["memo"]]).strip() if "memo" in column_indices else ""
            if memo == "nan": memo = ""
            qty = 1
            if "qty" in column_indices:
                try: qty = int(float(row[column_indices["qty"]]))
                except: qty = 1
            
            item = {
                "id": str(uuid.uuid4()), "ordered": (qty > 0), "name": name, "phone": phone, "address": address,
                "qty": qty, "memo": memo, "sender_name": "", "sender_phone": "", "sender_addr": ""
            }
            extracted_data.append(item)
        return pd.DataFrame(extracted_data), None
    except Exception as e: return None, f"분석 오류: {str(e)}"

# =============================================================================
# 🖥️ [UI] 메인 화면
# =============================================================================
st.title("🍊 감귤 농장")

tab1, tab2, tab3, tab4 = st.tabs(["📋 명단", "🚚 주문", "📊 통계", "⚙️ 설정"])

# --- Tab 1: 고객 관리 ---
with tab1:
    with st.expander("📂 엑셀 불러오기"):
        up_file = st.file_uploader("엑셀 업로드", type=["xlsx", "xls", "xlsm"])
        if up_file:
            if st.button("합치기", type="primary"):
                new_df, err = smart_import_ai(up_file)
                if err: st.error(err)
                else:
                    # 중복 제거
                    existing_keys = set(zip(st.session_state.df['name'], st.session_state.df['phone']))
                    filtered = [r for _, r in new_df.iterrows() if (r['name'], r['phone']) not in existing_keys]
                    
                    if filtered:
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(filtered)], ignore_index=True)
                        st.session_state.df.fillna("", inplace=True)
                        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                        save_all()
                        st.success(f"{len(filtered)}명 추가!")
                    else: st.warning("이미 다 있어요.")
                    st.rerun()

    with st.expander("➕ 직접 등록"):
        with st.form("new"):
            c1, c2 = st.columns(2)
            n = c1.text_input("이름")
            p = c2.text_input("전화")
            a = st.text_input("주소")
            c3, c4 = st.columns(2)
            q = c3.number_input("수량", min_value=0)
            m = c4.text_input("메모")
            if st.form_submit_button("등록"):
                if n:
                    row = {"id":str(uuid.uuid4()), "ordered":(q>0), "name":n, "phone":p, "address":a, "qty":q, "memo":m, "sender_name":"", "sender_phone":"", "sender_addr":""}
                    st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([row])], ignore_index=True)
                    st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                    save_all()
                    st.success("완료!")
                    st.rerun()

    st.divider()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 체크 해제 (수량0)", help="초기화"):
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.toast("초기화됨")
            st.rerun()

    st.session_state.df.fillna("", inplace=True)

    # [핵심] 모바일 초밀착 뷰 설정
    edited_df = st.data_editor(
        st.session_state.df,
        column_config={
            "ordered": st.column_config.CheckboxColumn("✅", width="small"),  # 이모지로 변경
            "name": st.column_config.TextColumn("이름", width="small"),
            "phone": st.column_config.TextColumn("📞", width="small"),      # 이모지로 변경
            "qty": st.column_config.NumberColumn("📦", width="small"),      # 이모지로 변경
            "address": st.column_config.TextColumn("주소", width="medium"),
            "memo": st.column_config.TextColumn("📝", width="small"),       # 이모지로 변경
            "id": None, "sender_name": None, "sender_phone": None, "sender_addr": None
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_main"
    )

    if not edited_df.equals(st.session_state.df):
        common_idx = st.session_state.df.index.intersection(edited_df.index)
        for i in common_idx:
            old = st.session_state.df.loc[i]
            new = edited_df.loc[i]
            if not old['ordered'] and new['ordered'] and new['qty'] == 0: edited_df.at[i, 'qty'] = 1
            elif old['ordered'] and not new['ordered']: edited_df.at[i, 'qty'] = 0
            elif new['qty'] > 0 and not new['ordered']: edited_df.at[i, 'ordered'] = True
            elif new['qty'] == 0 and new['ordered']: edited_df.at[i, 'ordered'] = False
        
        st.session_state.df = edited_df
        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
        save_all()
        st.rerun()

# --- Tab 2: 주문 현황 ---
with tab2:
    orders = st.session_state.df[st.session_state.df['ordered']==True].copy()
    st.metric("주문 합계", f"{len(orders)}건", f"{orders['qty'].sum()}박스")
    
    if not orders.empty:
        edited_orders = st.data_editor(
            orders,
            column_config={
                "name": st.column_config.TextColumn("이름", width="small"),
                "qty": st.column_config.NumberColumn("📦", width="small"),
                "phone": st.column_config.TextColumn("📞", width="small"),
                "address": st.column_config.TextColumn("주소", width="medium"),
                "memo": st.column_config.TextColumn("📝", width="small"),
                "id": None, "ordered": None, "sender_name": None, "sender_phone": None, "sender_addr": None
            },
            use_container_width=True,
            hide_index=True,
            key="order_editor"
        )

        if not edited_orders.equals(orders):
            st.session_state.df.update(edited_orders)
            zero_qty = edited_orders[edited_orders['qty'] == 0].index
            if not zero_qty.empty: st.session_state.df.loc[zero_qty, 'ordered'] = False
            save_all()
            st.rerun()

        st.divider()
        if st.button("🏁 주문 마감 (저장&리셋)", type="primary"):
            record = orders[["name", "phone", "qty"]].copy()
            record['date'] = datetime.now().strftime("%Y-%m-%d")
            st.session_state.history = pd.concat([st.session_state.history, record], ignore_index=True)
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.success("마감 완료!")
            st.rerun()
    else:
        st.info("주문 없음")

# --- Tab 3: 통계 ---
with tab3:
    c1, c2 = st.columns([3, 1])
    c1.subheader("🏆 VIP")
    if c2.button("🗑️ 삭제"):
        st.session_state.history = pd.DataFrame(columns=["date", "name", "phone", "qty"])
        save_all()
        st.rerun()

    if not st.session_state.history.empty:
        stats = st.session_state.history.groupby(["name", "phone"])['qty'].sum().reset_index()
        stats = stats.sort_values(by='qty', ascending=False).reset_index(drop=True)
        stats.index += 1
        st.dataframe(stats, use_container_width=True, 
                     column_config={
                         "name": st.column_config.TextColumn("이름", width="small"),
                         "phone": st.column_config.TextColumn("전화", width="medium"),
                         "qty": st.column_config.ProgressColumn("누적", format="%d", width="medium")
                     })
    else:
        st.info("기록 없음")

# --- Tab 4: 설정/송장 ---
with tab4:
    with st.expander("기본 정보 설정", expanded=True):
        with st.form("def_sender"):
            c1, c2 = st.columns(2)
            sn = c1.text_input("성함", st.session_state.sender['name'])
            sp = c2.text_input("연락처", st.session_state.sender['phone'])
            sa = st.text_input("주소", st.session_state.sender['addr'])
            if st.form_submit_button("저장"):
                st.session_state.sender = {"name":sn, "phone":sp, "addr":sa}
                save_all()
                st.success("저장됨")

    st.divider()
    st.write("📄 송장 편집")
    
    orders_active = st.session_state.df[st.session_state.df['ordered']==True].copy()
    
    if not orders_active.empty:
        def_s = st.session_state.sender
        for col, def_val in [('sender_name', def_s['name']), ('sender_phone', def_s['phone']), ('sender_addr', def_s['addr'])]:
            orders_active[col] = orders_active[col].replace("", pd.NA).fillna(def_val)

        orders_active = orders_active.sort_values(by=['sender_name', 'name'])

        edited_inv = st.data_editor(
            orders_active,
            column_config={
                "sender_name": st.column_config.TextColumn("보내는분", width="small"),
                "sender_phone": st.column_config.TextColumn("보내는전화", width="small"),
                "sender_addr": st.column_config.TextColumn("보내는주소", width="medium"),
                "name": st.column_config.TextColumn("받는분", disabled=True, width="small"),
                "phone": st.column_config.TextColumn("받는전화", disabled=True, width="small"),
                "address": st.column_config.TextColumn("받는주소", disabled=True, width="medium"),
                "qty": st.column_config.NumberColumn("📦", disabled=True, width="small"),
                "memo": st.column_config.TextColumn("📝", width="small"),
                "id": None, "ordered": None
            },
            column_order=["sender_name", "sender_phone", "sender_addr", "name", "phone", "address", "qty", "memo"],
            hide_index=True,
            use_container_width=True,
            key="inv_editor"
        )
        
        if not edited_inv.equals(orders_active):
            st.session_state.df.update(edited_inv)
            save_all()
            st.rerun()

        st.markdown("---")
        st.write("👀 미리보기")
        
        grouped = edited_inv.groupby(['sender_name', 'sender_phone', 'sender_addr'])
        for (s_name, s_phone, s_addr), group in grouped:
            st.markdown(f"<div class='sender-header'>📤 {s_name} ({s_phone})<br><span style='font-size:0.8em; font-weight:normal;'>{s_addr}</span></div>", unsafe_allow_html=True)
            
            group_key = f"preview_{s_name}_{s_phone}"
            edited_group = st.data_editor(
                group[['name', 'phone', 'address', 'qty', 'memo']],
                column_config={
                    "name": st.column_config.TextColumn("받는분", width="small", disabled=True),
                    "phone": st.column_config.TextColumn("전화", width="small", disabled=True),
                    "address": st.column_config.TextColumn("주소", width="medium", disabled=True),
                    "qty": st.column_config.NumberColumn("📦", width="small", disabled=True), 
                    "memo": st.column_config.TextColumn("📝", width="small")
                },
                use_container_width=True,
                hide_index=True,
                key=group_key
            )
            if not edited_group.equals(group[['name', 'phone', 'address', 'qty', 'memo']]):
                st.session_state.df.update(edited_group)
                save_all()
                st.rerun()

        def to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_rows = []
                for _, r in df.iterrows():
                    final_rows.append({
                        "보내는분": r['sender_name'], "보내는전화": r['sender_phone'], "보내는주소": r['sender_addr'],
                        "받는분": r['name'], "받는전화": r['phone'], "받는주소": r['address'],
                        "수량": r['qty'], "메모": r['memo']
                    })
                pd.DataFrame(final_rows).to_excel(writer, index=False)
            return output.getvalue()

        st.markdown("---")
        st.download_button(
            label="📥 엑셀 송장 다운로드",
            data=to_excel(edited_inv),
            file_name=f"송장_{datetime.now().strftime('%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.info("주문 없음")
