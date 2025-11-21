'''
import streamlit as st
import pandas as pd
import uuid
import io
import os
from datetime import datetime

# =============================================================================
# 📱 [설정] 페이지 및 디자인 (글씨 크기 확대)
# =============================================================================
st.set_page_config(
    page_title="감귤 농장 Manager",
    page_icon="🍊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 글씨 크기 및 디자인 커스텀
st.markdown("""
    <style>
    /* 전체 글씨 크기 업그레이드 */
    html, body, [class*="css"] {
        font-size: 18px !important;
    }
    /* 버튼 스타일 */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 4em;
        font-size: 18px !important;
        font-weight: bold;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    /* 입력창 글씨 크기 */
    .stTextInput > div > div > input {
        font-size: 18px !important;
    }
    /* 표(DataFrame) 글씨 크기 */
    div[data-testid="stDataFrame"] {
        font-size: 16px !important;
    }
    /* 송장 그룹 헤더 */
    .sender-header {
        background-color: #FFF3E0;
        padding: 15px;
        border-radius: 10px;
        border-left: 6px solid #FF6F00;
        margin-top: 25px;
        margin-bottom: 10px;
        font-weight: bold;
        font-size: 1.2em;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 💾 [데이터베이스] 데이터 관리 엔진
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
                
                # 이름순 정렬
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
            "name": ["이름", "성함", "고객명", "받는분", "수령인"],
            "phone": ["전화", "연락처", "H.P", "Mobile"],
            "address": ["주소", "배송지", "수령지"],
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

        if best_header_row == -1:
            return None, "데이터 시작 위치를 찾지 못했습니다."

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
                "id": str(uuid.uuid4()), "ordered": (qty > 0),
                "name": name, "phone": phone, "address": address,
                "qty": qty, "memo": memo,
                "sender_name": "", "sender_phone": "", "sender_addr": ""
            }
            extracted_data.append(item)

        return pd.DataFrame(extracted_data), None

    except Exception as e:
        return None, f"분석 오류: {str(e)}"

# =============================================================================
# 🖥️ [UI] 메인 화면
# =============================================================================
st.title("🍊 감귤 농장 Manager")

tab1, tab2, tab3, tab4 = st.tabs(["📋 고객 관리", "🚚 주문 현황", "📊 누적 통계", "⚙️ 설정/송장"])

# --- Tab 1: 고객 관리 ---
with tab1:
    with st.expander("📂 엑셀 파일 불러오기 (Smart)", expanded=True):
        up_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls", "xlsm"])
        if up_file:
            if st.button("데이터 분석 및 합치기", type="primary"):
                new_df, err = smart_import_ai(up_file)
                if err: 
                    st.error(err)
                else:
                    # [중복 제거 로직]
                    # 기존 데이터의 (이름, 전화번호) 집합 생성
                    existing_keys = set(zip(st.session_state.df['name'], st.session_state.df['phone']))
                    
                    filtered_rows = []
                    duplicate_count = 0
                    
                    for _, row in new_df.iterrows():
                        if (row['name'], row['phone']) not in existing_keys:
                            filtered_rows.append(row)
                        else:
                            duplicate_count += 1
                    
                    if filtered_rows:
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(filtered_rows)], ignore_index=True)
                        st.session_state.df.fillna("", inplace=True)
                        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                        save_all()
                        
                        msg = f"✅ 총 {len(new_df)}명 중 {len(filtered_rows)}명 추가 완료!"
                        if duplicate_count > 0:
                            msg += f" (중복 {duplicate_count}명 제외됨)"
                        st.success(msg)
                    else:
                        st.warning(f"모든 데이터({len(new_df)}명)가 이미 존재합니다.")
                        
                    st.rerun()

    with st.expander("➕ 신규 고객 등록"):
        with st.form("new_cust"):
            c1, c2 = st.columns(2)
            n = c1.text_input("이름")
            p = c2.text_input("전화번호")
            a = st.text_input("주소")
            c3, c4 = st.columns(2)
            q = c3.number_input("수량", min_value=0, value=0)
            m = c4.text_input("메모")
            if st.form_submit_button("등록"):
                if n:
                    # 신규 등록 시에도 중복 체크
                    is_dup = not st.session_state.df[
                        (st.session_state.df['name'] == n) & 
                        (st.session_state.df['phone'] == p)
                    ].empty
                    
                    if is_dup:
                        st.error("이미 존재하는 고객입니다.")
                    else:
                        row = {"id":str(uuid.uuid4()), "ordered":(q>0), "name":n, "phone":p, "address":a, "qty":q, "memo":m, "sender_name":"", "sender_phone":"", "sender_addr":""}
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([row])], ignore_index=True)
                        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                        save_all()
                        st.success(f"{n}님 등록 완료!")
                        st.rerun()

    st.divider()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 주문 상태 초기화 (수량 0)", help="모든 주문 체크 해제"):
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.toast("주문 상태가 초기화되었습니다.")
            st.rerun()

    st.session_state.df.fillna("", inplace=True)

    # [모든 데이터 수정 가능] - 고객 관리
    edited_df = st.data_editor(
        st.session_state.df,
        column_config={
            "ordered": st.column_config.CheckboxColumn("주문", width="small"),
            "name": st.column_config.TextColumn("이름", width="small"),
            "phone": st.column_config.TextColumn("전화번호", width="medium"),
            "address": st.column_config.TextColumn("주소", width="large"),
            "qty": st.column_config.NumberColumn("수량", width="small"),
            "memo": st.column_config.TextColumn("메모", width="medium"),
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
    st.metric("📦 현재 주문 합계", f"{len(orders)} 건", f"{orders['qty'].sum()} 박스")
    
    if not orders.empty:
        # [모든 데이터 수정 가능] - 주문 현황
        # data_editor로 변경하여 이름, 전화번호, 주소 모두 수정 가능하게 함
        edited_orders = st.data_editor(
            orders,
            column_config={
                "name": st.column_config.TextColumn("이름"),
                "phone": st.column_config.TextColumn("전화번호"),
                "address": st.column_config.TextColumn("주소"),
                "qty": st.column_config.NumberColumn("수량", min_value=0),
                "memo": st.column_config.TextColumn("메모"),
                "id": None, "ordered": None, "sender_name": None, "sender_phone": None, "sender_addr": None
            },
            use_container_width=True,
            hide_index=True,
            key="order_editor"
        )

        if not edited_orders.equals(orders):
            st.session_state.df.update(edited_orders)
            # 수량이 0이 되면 주문 취소 처리
            zero_qty_indices = edited_orders[edited_orders['qty'] == 0].index
            if not zero_qty_indices.empty:
                st.session_state.df.loc[zero_qty_indices, 'ordered'] = False
            save_all()
            st.rerun()

        st.divider()
        if st.button("🏁 주문 마감 및 기록 저장", type="primary"):
            record = orders[["name", "phone", "qty"]].copy()
            record['date'] = datetime.now().strftime("%Y-%m-%d")
            st.session_state.history = pd.concat([st.session_state.history, record], ignore_index=True)
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.success("마감 완료! 누적 통계에 반영되었습니다.")
            st.rerun()
    else:
        st.info("주문이 없습니다.")

# --- Tab 3: 통계 ---
with tab3:
    col_stat1, col_stat2 = st.columns([4, 1])
    with col_stat1:
        st.subheader("🏆 VIP 고객")
    with col_stat2:
        if st.button("🗑️ 통계 초기화", type="secondary"):
            if not st.session_state.history.empty:
                st.session_state.history = pd.DataFrame(columns=["date", "name", "phone", "qty"])
                save_all()
                st.success("초기화되었습니다.")
                st.rerun()
            else:
                st.toast("기록이 없습니다.")

    if not st.session_state.history.empty:
        stats = st.session_state.history.groupby(["name", "phone"])['qty'].sum().reset_index()
        stats = stats.sort_values(by='qty', ascending=False).reset_index(drop=True)
        stats.index += 1
        st.dataframe(stats, use_container_width=True, column_config={"qty": st.column_config.ProgressColumn("누적 주문량", format="%d 박스")})
    else:
        st.info("기록이 없습니다.")

# --- Tab 4: 설정/송장 ---
with tab4:
    st.subheader("1. 기본 보내는 사람")
    with st.form("default_sender"):
        c1, c2 = st.columns(2)
        sn = c1.text_input("성함", st.session_state.sender['name'])
        sp = c2.text_input("연락처", st.session_state.sender['phone'])
        sa = st.text_input("주소", st.session_state.sender['addr'])
        if st.form_submit_button("저장"):
            st.session_state.sender = {"name":sn, "phone":sp, "addr":sa}
            save_all()
            st.success("저장되었습니다.")

    st.divider()
    st.subheader("2. 송장 출력 (개별 수정)")
    st.caption("※ 모든 항목을 클릭하여 수정할 수 있습니다.")
    
    orders_active = st.session_state.df[st.session_state.df['ordered']==True].copy()
    
    if not orders_active.empty:
        def_s = st.session_state.sender
        for col, def_val in [('sender_name', def_s['name']), ('sender_phone', def_s['phone']), ('sender_addr', def_s['addr'])]:
            orders_active[col] = orders_active[col].replace("", pd.NA).fillna(def_val)

        orders_active = orders_active.sort_values(by=['sender_name', 'name'])

        # [모든 데이터 수정 가능] - 송장 목록
        # disabled=True 옵션을 모두 제거하여 전체 수정 가능하게 함
        edited_inv = st.data_editor(
            orders_active,
            column_config={
                "sender_name": st.column_config.TextColumn("보내는분(수정)"),
                "sender_phone": st.column_config.TextColumn("보내는연락처(수정)"),
                "sender_addr": st.column_config.TextColumn("보내는주소(수정)"),
                "name": st.column_config.TextColumn("받는분(수정)"),
                "phone": st.column_config.TextColumn("받는연락처(수정)"),
                "address": st.column_config.TextColumn("받는주소(수정)"),
                "qty": st.column_config.NumberColumn("수량", disabled=True), # 수량은 여기서 바꾸면 헷갈리니 유지 (필요하면 풀어드림)
                "memo": st.column_config.TextColumn("메모(수정)"),
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
        st.subheader("3. 👀 송장 미리보기 (그룹별 확인)")
        
        grouped = edited_inv.groupby(['sender_name', 'sender_phone', 'sender_addr'])
        
        for (s_name, s_phone, s_addr), group in grouped:
            st.markdown(f"""
                <div class="sender-header">
                    📤 보내는 분: {s_name} (Tel: {s_phone})<br>
                    <span style="font-size:0.9em; font-weight:normal;">{s_addr}</span>
                </div>
            """, unsafe_allow_html=True)
            
            # [모든 데이터 수정 가능] - 미리보기 표
            # 여기도 disabled 제거
            group_key = f"preview_group_{s_name}_{s_phone}"
            edited_group = st.data_editor(
                group[['name', 'phone', 'address', 'qty', 'memo']],
                column_config={
                    "name": st.column_config.TextColumn("받는분"),
                    "phone": st.column_config.TextColumn("연락처"),
                    "address": st.column_config.TextColumn("주소"),
                    "qty": st.column_config.NumberColumn("수량", disabled=True), 
                    "memo": st.column_config.TextColumn("메모")
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
        st.info("주문이 없습니다.")
'''

import streamlit as st
import pandas as pd
import uuid
import io
import os
from datetime import datetime

# =============================================================================
# 📱 [설정] 페이지 및 모바일 최적화
# =============================================================================
st.set_page_config(
    page_title="감귤 농장 Manager",
    page_icon="🍊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 모바일 맞춤형 CSS
st.markdown("""
    <style>
    /* 버튼은 터치하기 좋게 큼직하게 유지 */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.8em;
        font-weight: bold;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        font-size: 16px;
    }
    /* 입력창도 터치하기 편하게 */
    .stTextInput > div > div > input {
        min-height: 45px;
    }
    /* 표(Grid)의 여백을 줄여서 더 많은 정보 표시 */
    [data-testid="stDataEditor"] div[data-testid="stVerticalBlock"] {
        gap: 0.5rem;
    }
    /* 송장 그룹 헤더 */
    .sender-header {
        background-color: #FFF3E0;
        padding: 12px;
        border-radius: 10px;
        border-left: 5px solid #FF6F00;
        margin-top: 20px;
        margin-bottom: 8px;
        font-weight: bold;
        font-size: 1.1em;
        line-height: 1.4;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 💾 [데이터베이스] 데이터 관리 엔진
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
                
                # 이름순 정렬
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
            "name": ["이름", "성함", "고객명", "받는분", "수령인"],
            "phone": ["전화", "연락처", "H.P", "Mobile"],
            "address": ["주소", "배송지", "수령지"],
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

        if best_header_row == -1:
            return None, "데이터 시작 위치를 찾지 못했습니다."

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
                "id": str(uuid.uuid4()), "ordered": (qty > 0),
                "name": name, "phone": phone, "address": address,
                "qty": qty, "memo": memo,
                "sender_name": "", "sender_phone": "", "sender_addr": ""
            }
            extracted_data.append(item)

        return pd.DataFrame(extracted_data), None

    except Exception as e:
        return None, f"분석 오류: {str(e)}"

# =============================================================================
# 🖥️ [UI] 메인 화면
# =============================================================================
st.title("🍊 감귤 농장 Manager")

tab1, tab2, tab3, tab4 = st.tabs(["📋 고객 관리", "🚚 주문 현황", "📊 누적 통계", "⚙️ 설정/송장"])

# --- Tab 1: 고객 관리 ---
with tab1:
    with st.expander("📂 엑셀 파일 불러오기 (Smart)", expanded=True):
        up_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx", "xls", "xlsm"])
        if up_file:
            if st.button("데이터 분석 및 합치기", type="primary"):
                new_df, err = smart_import_ai(up_file)
                if err: st.error(err)
                else:
                    existing_keys = set(zip(st.session_state.df['name'], st.session_state.df['phone']))
                    filtered_rows = []
                    duplicate_count = 0
                    
                    for _, row in new_df.iterrows():
                        if (row['name'], row['phone']) not in existing_keys:
                            filtered_rows.append(row)
                        else:
                            duplicate_count += 1
                    
                    if filtered_rows:
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(filtered_rows)], ignore_index=True)
                        st.session_state.df.fillna("", inplace=True)
                        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                        save_all()
                        msg = f"✅ {len(filtered_rows)}명 추가 완료!"
                        if duplicate_count > 0: msg += f" (중복 {duplicate_count}명 제외)"
                        st.success(msg)
                    else:
                        st.warning("이미 모든 데이터가 존재합니다.")
                    st.rerun()

    with st.expander("➕ 신규 고객 등록"):
        with st.form("new_cust"):
            c1, c2 = st.columns(2)
            n = c1.text_input("이름")
            p = c2.text_input("전화번호")
            a = st.text_input("주소")
            c3, c4 = st.columns(2)
            q = c3.number_input("수량", min_value=0, value=0)
            m = c4.text_input("메모")
            if st.form_submit_button("등록"):
                if n:
                    is_dup = not st.session_state.df[(st.session_state.df['name'] == n) & (st.session_state.df['phone'] == p)].empty
                    if is_dup: st.error("이미 존재하는 고객입니다.")
                    else:
                        row = {"id":str(uuid.uuid4()), "ordered":(q>0), "name":n, "phone":p, "address":a, "qty":q, "memo":m, "sender_name":"", "sender_phone":"", "sender_addr":""}
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([row])], ignore_index=True)
                        st.session_state.df = st.session_state.df.sort_values(by='name').reset_index(drop=True)
                        save_all()
                        st.success(f"{n}님 등록 완료!")
                        st.rerun()

    st.divider()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 주문 초기화 (수량 0)", help="모든 주문 체크 해제"):
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.toast("초기화되었습니다.")
            st.rerun()

    st.session_state.df.fillna("", inplace=True)

    # [모바일 최적화] 너비를 "small"로 통일하여 한 화면에 최대한 많이 표시
    edited_df = st.data_editor(
        st.session_state.df,
        column_config={
            "ordered": st.column_config.CheckboxColumn("주문", width="small"),
            "name": st.column_config.TextColumn("이름", width="small"),
            "phone": st.column_config.TextColumn("전화", width="small"), # 헤더 축약
            "address": st.column_config.TextColumn("주소", width="medium"),
            "qty": st.column_config.NumberColumn("수량", width="small"),
            "memo": st.column_config.TextColumn("메모", width="small"),
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
    st.metric("📦 현재 주문 합계", f"{len(orders)} 건", f"{orders['qty'].sum()} 박스")
    
    if not orders.empty:
        # [모바일 최적화] 너비 small 적용
        edited_orders = st.data_editor(
            orders,
            column_config={
                "name": st.column_config.TextColumn("이름", width="small"),
                "phone": st.column_config.TextColumn("전화", width="small"),
                "address": st.column_config.TextColumn("주소", width="medium"),
                "qty": st.column_config.NumberColumn("수량", min_value=0, width="small"),
                "memo": st.column_config.TextColumn("메모", width="small"),
                "id": None, "ordered": None, "sender_name": None, "sender_phone": None, "sender_addr": None
            },
            use_container_width=True,
            hide_index=True,
            key="order_editor"
        )

        if not edited_orders.equals(orders):
            st.session_state.df.update(edited_orders)
            zero_qty_indices = edited_orders[edited_orders['qty'] == 0].index
            if not zero_qty_indices.empty:
                st.session_state.df.loc[zero_qty_indices, 'ordered'] = False
            save_all()
            st.rerun()

        st.divider()
        if st.button("🏁 주문 마감 및 기록 저장", type="primary"):
            record = orders[["name", "phone", "qty"]].copy()
            record['date'] = datetime.now().strftime("%Y-%m-%d")
            st.session_state.history = pd.concat([st.session_state.history, record], ignore_index=True)
            st.session_state.df['ordered'] = False
            st.session_state.df['qty'] = 0
            save_all()
            st.success("마감 완료! 누적 통계에 반영되었습니다.")
            st.rerun()
    else:
        st.info("주문이 없습니다.")

# --- Tab 3: 통계 ---
with tab3:
    col_stat1, col_stat2 = st.columns([4, 1])
    with col_stat1:
        st.subheader("🏆 VIP 고객")
    with col_stat2:
        if st.button("🗑️ 통계 초기화", type="secondary"):
            if not st.session_state.history.empty:
                st.session_state.history = pd.DataFrame(columns=["date", "name", "phone", "qty"])
                save_all()
                st.success("초기화되었습니다.")
                st.rerun()
            else:
                st.toast("기록이 없습니다.")

    if not st.session_state.history.empty:
        stats = st.session_state.history.groupby(["name", "phone"])['qty'].sum().reset_index()
        stats = stats.sort_values(by='qty', ascending=False).reset_index(drop=True)
        stats.index += 1
        st.dataframe(stats, use_container_width=True, column_config={
            "name": st.column_config.TextColumn("이름", width="small"),
            "phone": st.column_config.TextColumn("전화", width="medium"),
            "qty": st.column_config.ProgressColumn("누적량", format="%d 박스", width="medium")
        })
    else:
        st.info("기록이 없습니다.")

# --- Tab 4: 설정/송장 ---
with tab4:
    st.subheader("1. 기본 보내는 사람")
    with st.form("default_sender"):
        c1, c2 = st.columns(2)
        sn = c1.text_input("성함", st.session_state.sender['name'])
        sp = c2.text_input("연락처", st.session_state.sender['phone'])
        sa = st.text_input("주소", st.session_state.sender['addr'])
        if st.form_submit_button("저장"):
            st.session_state.sender = {"name":sn, "phone":sp, "addr":sa}
            save_all()
            st.success("저장되었습니다.")

    st.divider()
    st.subheader("2. 송장 출력 (개별 수정)")
    st.caption("※ 수정이 필요한 항목을 클릭하세요.")
    
    orders_active = st.session_state.df[st.session_state.df['ordered']==True].copy()
    
    if not orders_active.empty:
        def_s = st.session_state.sender
        for col, def_val in [('sender_name', def_s['name']), ('sender_phone', def_s['phone']), ('sender_addr', def_s['addr'])]:
            orders_active[col] = orders_active[col].replace("", pd.NA).fillna(def_val)

        orders_active = orders_active.sort_values(by=['sender_name', 'name'])

        # [모바일 최적화] 너비 조정
        edited_inv = st.data_editor(
            orders_active,
            column_config={
                "sender_name": st.column_config.TextColumn("보내는분", width="small"),
                "sender_phone": st.column_config.TextColumn("보내는전화", width="small"),
                "sender_addr": st.column_config.TextColumn("보내는주소", width="medium"),
                "name": st.column_config.TextColumn("받는분", disabled=True, width="small"),
                "phone": st.column_config.TextColumn("받는전화", disabled=True, width="small"),
                "address": st.column_config.TextColumn("받는주소", disabled=True, width="medium"),
                "qty": st.column_config.NumberColumn("수량", disabled=True, width="small"),
                "memo": st.column_config.TextColumn("메모", width="small"),
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
        st.subheader("3. 👀 송장 미리보기 (그룹별)")
        
        grouped = edited_inv.groupby(['sender_name', 'sender_phone', 'sender_addr'])
        
        for (s_name, s_phone, s_addr), group in grouped:
            st.markdown(f"""
                <div class="sender-header">
                    📤 {s_name} ({s_phone})<br>
                    <span style="font-size:0.9em; font-weight:normal;">{s_addr}</span>
                </div>
            """, unsafe_allow_html=True)
            
            group_key = f"preview_group_{s_name}_{s_phone}"
            edited_group = st.data_editor(
                group[['name', 'phone', 'address', 'qty', 'memo']],
                column_config={
                    "name": st.column_config.TextColumn("받는분", width="small", disabled=True),
                    "phone": st.column_config.TextColumn("연락처", width="small", disabled=True),
                    "address": st.column_config.TextColumn("주소", width="medium", disabled=True),
                    "qty": st.column_config.NumberColumn("수량", width="small", disabled=True), 
                    "memo": st.column_config.TextColumn("메모", width="small")
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
        st.info("주문이 없습니다.")
