import streamlit as st
import pandas as pd
import uuid
import io
import os
import shutil
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
    /* 1. 버튼, 입력창은 터치하기 쉽게 큼직하게 유지 */
    .stButton>button, .stTextInput input, .stNumberInput input {
        min-height: 45px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }
    .stButton>button {
        background-color: #FF6F00 !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    /* 2. 표(Grid)는 정보를 많이 보여주기 위해 슬림하게 조정 */
    div[data-testid="stDataEditor"] table, div[data-testid="stDataFrame"] table {
        font-size: 13px !important; /* 표 글씨는 약간 작게 */
    }
    
    /* 3. 표의 칸 여백을 줄여서(Autosize 효과) 모바일 폭에 맞춤 */
    div[data-testid="stDataEditor"] th, div[data-testid="stDataEditor"] td {
        padding: 8px 4px !important; /* 좌우 여백 최소화 */
    }
    
    /* 송장 그룹 헤더 */
    .sender-header {
        background-color: #FFF3E0;
        padding: 12px;
        border-radius: 8px;
        border-left: 5px solid #FF6F00;
        margin-top: 20px;
        margin-bottom: 8px;
        font-weight: bold;
        font-size: 15px;
        line-height: 1.4;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 💾 [데이터베이스 경로 및 스키마]
# =============================================================================
DB_FILE = "customer_db.csv"
HISTORY_FILE = "order_history.csv"
CONFIG_FILE = "config.csv"

REQUIRED_CUSTOMER_COLS = [
    "id", "ordered", "name", "phone", "address",
    "qty", "memo", "sender_name", "sender_phone", "sender_addr"
]

REQUIRED_HISTORY_COLS = ["date", "name", "phone", "qty"]
REQUIRED_SENDER_COLS = ["name", "phone", "addr"]

# -----------------------------------------------------------------------------
# 💾 안전 저장 유틸: temp 파일 + 백업 + 빈 DF 보호
# -----------------------------------------------------------------------------
def safe_save_csv(path: str, df: pd.DataFrame, protect_if_exists_and_empty: bool = True):
    """
    CSV 안전 저장:
      1) df가 비어 있고 기존 파일이 존재하면 -> 원본 보호 (저장 안함)
      2) 임시 파일에 먼저 쓰고 → 성공하면 원본 백업 → 임시파일로 교체
    """
    if df is None:
        return

    # df가 비어있고, 기존 파일은 있는 경우: 보호 모드
    if protect_if_exists_and_empty and os.path.exists(path) and df.empty:
        # 로그 정도만 남김 (Streamlit 로그에 찍힘)
        print(f"[safe_save_csv] {path} 보호: empty DF로 기존 파일을 덮어쓰지 않음.")
        return

    tmp_path = path + ".tmp"
    backup_path = path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    try:
        df.to_csv(tmp_path, index=False)

        # 기존 파일이 있으면 백업
        if os.path.exists(path):
            try:
                shutil.copy2(path, backup_path)
            except Exception as e:
                print(f"[safe_save_csv] 백업 실패({path} -> {backup_path}): {e}")

        # tmp를 원본으로 교체 (원자적 교체에 가까움)
        os.replace(tmp_path, path)
    except Exception as e:
        # tmp가 남아있으면 삭제 시도
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise e

# -----------------------------------------------------------------------------
# 📐 스키마 정리 유틸
# -----------------------------------------------------------------------------
def ensure_customer_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        # 완전히 새로
        df = pd.DataFrame(columns=REQUIRED_CUSTOMER_COLS)

    # 필요한 컬럼 보장
    for col in REQUIRED_CUSTOMER_COLS:
        if col not in df.columns:
            if col == "ordered":
                df[col] = False
            elif col == "qty":
                df[col] = 0
            else:
                df[col] = ""

    # 형변환
    df["ordered"] = df["ordered"].apply(lambda x: str(x).lower() in ("true", "1", "y", "yes"))
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)

    # id가 비어 있으면 uuid 채우기
    if df["id"].isna().any() or (df["id"] == "").any():
        df["id"] = df["id"].apply(lambda x: x if isinstance(x, str) and x.strip() else str(uuid.uuid4()))

    # 마지막으로 컬럼 순서 정리
    df = df[REQUIRED_CUSTOMER_COLS]
    return df.reset_index(drop=True)


def ensure_history_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=REQUIRED_HISTORY_COLS)
    for col in REQUIRED_HISTORY_COLS:
        if col not in df.columns:
            if col == "qty":
                df[col] = 0
            else:
                df[col] = ""
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    return df[REQUIRED_HISTORY_COLS].reset_index(drop=True)


def ensure_sender_schema(d: dict) -> dict:
    if d is None:
        d = {}
    for col in REQUIRED_SENDER_COLS:
        if col not in d:
            d[col] = ""
    return d

# =============================================================================
# 🔁 초기 상태 로드
# =============================================================================
def init_state():
    # --- 고객 DB ---
    if "df" not in st.session_state:
        if os.path.exists(DB_FILE):
            try:
                raw = pd.read_csv(DB_FILE, dtype=str)
                st.session_state.df = ensure_customer_schema(raw)
            except Exception as e:
                print(f"[init_state] DB_FILE 로드 실패: {e}")
                st.session_state.df = ensure_customer_schema(pd.DataFrame())
        else:
            st.session_state.df = ensure_customer_schema(pd.DataFrame())

    # --- 주문 히스토리 ---
    if "history" not in st.session_state:
        if os.path.exists(HISTORY_FILE):
            try:
                raw_h = pd.read_csv(HISTORY_FILE)
                st.session_state.history = ensure_history_schema(raw_h)
            except Exception as e:
                print(f"[init_state] HISTORY_FILE 로드 실패: {e}")
                st.session_state.history = ensure_history_schema(pd.DataFrame())
        else:
            st.session_state.history = ensure_history_schema(pd.DataFrame())

    # --- 송장 기본 설정 ---
    if "sender" not in st.session_state:
        if os.path.exists(CONFIG_FILE):
            try:
                cfg = pd.read_csv(CONFIG_FILE).iloc[0].to_dict()
                st.session_state.sender = ensure_sender_schema(cfg)
            except Exception as e:
                print(f"[init_state] CONFIG_FILE 로드 실패: {e}")
                st.session_state.sender = ensure_sender_schema({"name": "제주감귤농장", "phone": "010-0000-0000", "addr": "제주도"})
        else:
            st.session_state.sender = ensure_sender_schema({"name": "제주감귤농장", "phone": "010-0000-0000", "addr": "제주도"})

def save_all():
    """모든 CSV를 안전하게 저장"""
    # 항상 스키마 보정 후 저장
    st.session_state.df = ensure_customer_schema(st.session_state.df)
    st.session_state.history = ensure_history_schema(st.session_state.history)
    st.session_state.sender = ensure_sender_schema(st.session_state.sender)

    # DB: 기존 파일이 있을 때 empty DF로 덮어쓰지 않도록 보호
    safe_save_csv(DB_FILE, st.session_state.df, protect_if_exists_and_empty=True)
    safe_save_csv(HISTORY_FILE, st.session_state.history, protect_if_exists_and_empty=False)
    # sender 설정은 DataFrame 하나 만들어서 저장
    sender_df = pd.DataFrame([st.session_state.sender])
    safe_save_csv(CONFIG_FILE, sender_df, protect_if_exists_and_empty=False)

init_state()

# =============================================================================
# 🧠 [Logic] 스마트 엑셀 로더
# =============================================================================
def smart_import_ai(file):
    try:
        df_raw = pd.read_excel(file, header=None)
        keywords = {
            "name": ["이름", "성함", "고객명", "받는분"],
            "phone": ["전화", "연락처", "H.P", "Mobile", "핸드폰"],
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
                if clean_val == "nan":
                    continue
                for key, synonyms in keywords.items():
                    if key in current_mapping:
                        continue
                    for s in synonyms:
                        if s.lower() in clean_val:
                            current_mapping[key] = col_idx
                            current_matches += 1
                            break
            if current_matches > max_matches and ("name" in current_mapping or "phone" in current_mapping):
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
            except KeyError:
                continue

            if raw_name == "nan" or raw_name.strip() == "":
                continue
            name = raw_name.strip()

            phone = ""
            if "phone" in column_indices:
                phone = str(row[column_indices["phone"]]).strip()
                if phone == "nan":
                    phone = ""

            address = ""
            if "address" in column_indices:
                address = str(row[column_indices["address"]]).strip()
                if address == "nan":
                    address = ""

            memo = ""
            if "memo" in column_indices:
                memo = str(row[column_indices["memo"]]).strip()
                if memo == "nan":
                    memo = ""

            qty = 1
            if "qty" in column_indices:
                try:
                    qty_val = row[column_indices["qty"]]
                    qty = int(float(qty_val))
                except Exception:
                    qty = 1
            
            item = {
                "id": str(uuid.uuid4()),
                "ordered": (qty > 0),
                "name": name,
                "phone": phone,
                "address": address,
                "qty": qty,
                "memo": memo,
                "sender_name": "",
                "sender_phone": "",
                "sender_addr": ""
            }
            extracted_data.append(item)

        if not extracted_data:
            return None, "추출할 데이터가 없습니다."

        new_df = pd.DataFrame(extracted_data)
        new_df = ensure_customer_schema(new_df)
        return new_df, None
    except Exception as e:
        return None, f"분석 오류: {str(e)}"

# =============================================================================
# 🖥️ [UI] 메인 화면
# =============================================================================
st.title("🍊 감귤 농장")

tab1, tab2, tab3, tab4 = st.tabs(["📋 명단", "🚚 주문", "📊 통계", "⚙️ 설정"])

# --- Tab 1: 고객 관리 ---
with tab1:
    with st.expander("📂 엑셀 불러오기 (Smart)", expanded=True):
        up_file = st.file_uploader("엑셀 업로드", type=["xlsx", "xls", "xlsm"])
        if up_file:
            if st.button("합치기", type="primary"):
                new_df, err = smart_import_ai(up_file)
                if err:
                    st.error(err)
                else:
                    # 중복 제거 (name+phone 기준)
                    base_df = ensure_customer_schema(st.session_state.df.copy())
                    existing_keys = set(zip(base_df["name"], base_df["phone"]))
                    filtered_rows = [
                        r for _, r in new_df.iterrows()
                        if (r["name"], r["phone"]) not in existing_keys
                    ]

                    if filtered_rows:
                        add_df = pd.DataFrame(filtered_rows)
                        merged = pd.concat([base_df, add_df], ignore_index=True)
                        merged = ensure_customer_schema(merged)
                        st.session_state.df = merged.sort_values(by="name").reset_index(drop=True)
                        save_all()
                        st.success(f"{len(filtered_rows)}명 추가!")
                    else:
                        st.warning("이미 등록된 고객입니다.")
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
                    row = {
                        "id": str(uuid.uuid4()),
                        "ordered": (q > 0),
                        "name": n,
                        "phone": p,
                        "address": a,
                        "qty": int(q),
                        "memo": m,
                        "sender_name": "",
                        "sender_phone": "",
                        "sender_addr": ""
                    }
                    df = ensure_customer_schema(st.session_state.df.copy())
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                    df = ensure_customer_schema(df)
                    df = df.sort_values(by="name").reset_index(drop=True)
                    st.session_state.df = df
                    save_all()
                    st.success("등록 완료!")
                    st.rerun()
                else:
                    st.warning("이름은 필수입니다.")

    st.divider()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 체크 해제 (수량0)", help="초기화"):
            df = ensure_customer_schema(st.session_state.df.copy())
            df["ordered"] = False
            df["qty"] = 0
            st.session_state.df = df
            save_all()
            st.toast("초기화됨")
            st.rerun()

    st.session_state.df = ensure_customer_schema(st.session_state.df)
    st.session_state.df.fillna("", inplace=True)

    # [핵심] 모바일 최적화 뷰: 이모지 헤더 + small 너비
    edited_df = st.data_editor(
        st.session_state.df,
        column_config={
            "ordered": st.column_config.CheckboxColumn("✅", width="small"),
            "name": st.column_config.TextColumn("👤", width="small"),
            "phone": st.column_config.TextColumn("📞", width="small"),
            "qty": st.column_config.NumberColumn("📦", width="small"),
            "address": st.column_config.TextColumn("🏠", width="medium"),
            "memo": st.column_config.TextColumn("📝", width="small"),
            "sender_name": None,
            "sender_phone": None,
            "sender_addr": None,
            "id": None
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="editor_main"
    )

    # 데이터 변경 감지 + 일관성 유지
    if not edited_df.equals(st.session_state.df):
        base_df = ensure_customer_schema(st.session_state.df.copy())
        edited_df = ensure_customer_schema(edited_df.copy())

        common_idx = base_df.index.intersection(edited_df.index)
        for i in common_idx:
            old = base_df.loc[i]
            new = edited_df.loc[i]

            # 주문-수량 관계 보정
            if (not old["ordered"]) and new["ordered"] and new["qty"] == 0:
                edited_df.at[i, "qty"] = 1
            elif old["ordered"] and (not new["ordered"]):
                edited_df.at[i, "qty"] = 0
            elif new["qty"] > 0 and (not new["ordered"]):
                edited_df.at[i, "ordered"] = True
            elif new["qty"] == 0 and new["ordered"]:
                edited_df.at[i, "ordered"] = False

        edited_df = ensure_customer_schema(edited_df)
        edited_df = edited_df.sort_values(by="name").reset_index(drop=True)

        st.session_state.df = edited_df
        save_all()
        st.rerun()

# --- Tab 2: 주문 현황 ---
with tab2:
    df_base = ensure_customer_schema(st.session_state.df.copy())
    orders = df_base[df_base["ordered"] == True].copy()

    st.metric("주문 합계", f"{len(orders)}건", f"{orders['qty'].sum()}박스")
    
    if not orders.empty:
        edited_orders = st.data_editor(
            orders,
            column_config={
                "name": st.column_config.TextColumn("👤", width="small"),
                "qty": st.column_config.NumberColumn("📦", width="small"),
                "phone": st.column_config.TextColumn("📞", width="small"),
                "address": st.column_config.TextColumn("🏠", width="medium"),
                "memo": st.column_config.TextColumn("📝", width="small"),
                "id": None,
                "ordered": None,
                "sender_name": None,
                "sender_phone": None,
                "sender_addr": None
            },
            use_container_width=True,
            hide_index=True,
            key="order_editor"
        )

        if not edited_orders.equals(orders):
            base_df = ensure_customer_schema(st.session_state.df.copy())
            edited_orders = ensure_customer_schema(edited_orders.copy())

            # base_df와 merge (id 기준)
            for _, row in edited_orders.iterrows():
                mask = base_df["id"] == row["id"]
                if mask.any():
                    base_df.loc[mask, ["qty", "memo"]] = row[["qty", "memo"]].values

            # qty 0이면 ordered=False
            zero_idx = base_df[base_df["qty"] == 0].index
            base_df.loc[zero_idx, "ordered"] = False

            base_df = ensure_customer_schema(base_df)
            st.session_state.df = base_df
            save_all()
            st.rerun()

        st.divider()
        if st.button("🏁 주문 마감 (저장&리셋)", type="primary"):
            record = orders[["name", "phone", "qty"]].copy()
            record["date"] = datetime.now().strftime("%Y-%m-%d")
            hist = ensure_history_schema(st.session_state.history.copy())
            hist = pd.concat([hist, record[REQUIRED_HISTORY_COLS]], ignore_index=True)
            st.session_state.history = ensure_history_schema(hist)

            df_reset = ensure_customer_schema(st.session_state.df.copy())
            df_reset["ordered"] = False
            df_reset["qty"] = 0
            st.session_state.df = df_reset

            save_all()
            st.success("마감 완료!")
            st.rerun()
    else:
        st.info("주문 없음")

# --- Tab 3: 통계 ---
with tab3:
    st.session_state.history = ensure_history_schema(st.session_state.history)
    c1, c2 = st.columns([3, 1])
    c1.subheader("🏆 VIP")
    if c2.button("🗑️ 전체 기록 삭제"):
        st.session_state.history = ensure_history_schema(pd.DataFrame())
        save_all()
        st.rerun()

    if not st.session_state.history.empty:
        stats = (
            st.session_state.history.groupby(["name", "phone"])["qty"]
            .sum()
            .reset_index()
        )
        stats = stats.sort_values(by="qty", ascending=False).reset_index(drop=True)
        stats.index += 1
        st.dataframe(
            stats,
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("이름", width="small"),
                "phone": st.column_config.TextColumn("전화", width="medium"),
                "qty": st.column_config.ProgressColumn("누적", format="%d", width="medium"),
            },
        )
    else:
        st.info("기록 없음")

# --- Tab 4: 설정/송장 ---
with tab4:
    with st.expander("기본 정보 설정", expanded=True):
        with st.form("def_sender"):
            c1, c2 = st.columns(2)
            sn = c1.text_input("성함", st.session_state.sender["name"])
            sp = c2.text_input("연락처", st.session_state.sender["phone"])
            sa = st.text_input("주소", st.session_state.sender["addr"])
            if st.form_submit_button("저장"):
                st.session_state.sender = ensure_sender_schema({"name": sn, "phone": sp, "addr": sa})
                save_all()
                st.success("저장됨")

    st.divider()
    st.write("📄 송장 편집")
    
    df_base = ensure_customer_schema(st.session_state.df.copy())
    orders_active = df_base[df_base["ordered"] == True].copy()
    
    if not orders_active.empty:
        def_s = ensure_sender_schema(st.session_state.sender)
        for col, def_val in [
            ("sender_name", def_s["name"]),
            ("sender_phone", def_s["phone"]),
            ("sender_addr", def_s["addr"]),
        ]:
            orders_active[col] = orders_active[col].replace("", pd.NA).fillna(def_val)

        orders_active = orders_active.sort_values(by=["sender_name", "name"])

        edited_inv = st.data_editor(
            orders_active,
            column_config={
                "sender_name": st.column_config.TextColumn("보냄👤", width="small"),
                "sender_phone": st.column_config.TextColumn("보냄📞", width="small"),
                "sender_addr": st.column_config.TextColumn("보냄🏠", width="medium"),
                "name": st.column_config.TextColumn("받음👤", disabled=True, width="small"),
                "phone": st.column_config.TextColumn("받음📞", disabled=True, width="small"),
                "address": st.column_config.TextColumn("받음🏠", disabled=True, width="medium"),
                "qty": st.column_config.NumberColumn("📦", disabled=True, width="small"),
                "memo": st.column_config.TextColumn("📝", width="small"),
                "id": None,
                "ordered": None,
                "sender_name": None,
                "sender_phone": None,
                "sender_addr": None
            },
            column_order=[
                "sender_name",
                "sender_phone",
                "sender_addr",
                "name",
                "phone",
                "address",
                "qty",
                "memo",
            ],
            hide_index=True,
            use_container_width=True,
            key="inv_editor",
        )
        
        if not edited_inv.equals(orders_active):
            base_df = ensure_customer_schema(st.session_state.df.copy())
            edited_inv = ensure_customer_schema(edited_inv.copy())

            for _, row in edited_inv.iterrows():
                mask = base_df["id"] == row["id"]
                if mask.any():
                    base_df.loc[mask, ["sender_name", "sender_phone", "sender_addr", "memo"]] = row[
                        ["sender_name", "sender_phone", "sender_addr", "memo"]
                    ].values

            st.session_state.df = ensure_customer_schema(base_df)
            save_all()
            st.rerun()

        st.markdown("---")
        st.write("👀 미리보기")
        
        grouped = edited_inv.groupby(["sender_name", "sender_phone", "sender_addr"])
        for (s_name, s_phone, s_addr), group in grouped:
            st.markdown(
                f"<div class='sender-header'>📤 {s_name} ({s_phone})<br>"
                f"<span style='font-size:0.8em; font-weight:normal;'>{s_addr}</span></div>",
                unsafe_allow_html=True,
            )
            
            group_key = f"preview_{s_name}_{s_phone}"
            edited_group = st.data_editor(
                group[["name", "phone", "address", "qty", "memo"]],
                column_config={
                    "name": st.column_config.TextColumn("👤", width="small", disabled=True),
                    "phone": st.column_config.TextColumn("📞", width="small", disabled=True),
                    "address": st.column_config.TextColumn("🏠", width="medium", disabled=True),
                    "qty": st.column_config.NumberColumn("📦", width="small", disabled=True),
                    "memo": st.column_config.TextColumn("📝", width="small"),
                },
                use_container_width=True,
                hide_index=True,
                key=group_key,
            )
            if not edited_group.equals(group[["name", "phone", "address", "qty", "memo"]]):
                base_df = ensure_customer_schema(st.session_state.df.copy())
                # group 행들에 대해서 memo만 업데이트
                for idx, row in edited_group.iterrows():
                    mask = base_df["id"] == group.loc[idx, "id"]
                    if mask.any():
                        base_df.loc[mask, "memo"] = row["memo"]
                st.session_state.df = ensure_customer_schema(base_df)
                save_all()
                st.rerun()

        def to_excel(df: pd.DataFrame):
            df = ensure_customer_schema(df.copy())
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                final_rows = []
                for _, r in df.iterrows():
                    final_rows.append(
                        {
                            "보내는분": r["sender_name"],
                            "보내는전화": r["sender_phone"],
                            "보내는주소": r["sender_addr"],
                            "받는분": r["name"],
                            "받는전화": r["phone"],
                            "받는주소": r["address"],
                            "수량": r["qty"],
                            "메모": r["memo"],
                        }
                    )
                pd.DataFrame(final_rows).to_excel(writer, index=False)
            return output.getvalue()

        st.markdown("---")
        st.download_button(
            label="📥 엑셀 송장 다운로드",
            data=to_excel(edited_inv),
            file_name=f"송장_{datetime.now().strftime('%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.info("주문 없음")
