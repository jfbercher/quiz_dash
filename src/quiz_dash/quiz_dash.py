import streamlit as st
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh
from streamlit_local_storage import LocalStorage
#from localStorage import LocalStorage
import base64
import zlib
import io
import json 

import matplotlib.pyplot as plt
# Labquiz functions import
from labquiz.main import QuizLab
from labquiz.putils import (
    readData, 
    check_integrity_msg, 
    check_hash_integrity, 
    correctQuizzesDf)

# Global variable initialization
local_storage = None
# Others
verbose = False

from i18n import init_i18n, set_language, get_translator
_ = init_i18n(default_lang="en")


# --- 1. INITIAL RESTORATION (TEXTS ONLY) ---
def set_defaults():
    global _
    st.session_state["selected_lang"] = "en"
    st.session_state["lang"] = "en"
    st.session_state["url"] = ""
    st.session_state["secret"] = ""
    st.session_state["group"] = _('All')
    st.session_state["bareme_str"] = "{}"
    st.session_state["maxtries"] = 3
    st.session_state["seuil"] = 0.0 
    st.session_state["exam_title"] = "" 
    st.session_state["params_str"] = "{'retries':2, 'exam_mode':False, 'test_mode':False}"

    # --- OTHER INITIALIZATION ---
    if "df_results" not in st.session_state:
        st.session_state.df_results = None
    if "df_final" not in st.session_state:
        st.session_state.df_final = None
    st.session_state.show_scores = False
    if "last_correction_update" not in st.session_state:
        st.session_state.last_correction_update = None
    if "refresh_key" not in st.session_state:
        st.session_state.refresh_key = 0
    if "uploader_version" not in st.session_state:
        st.session_state.uploader_version = 0
    if "last_processed_file" not in st.session_state:
        st.session_state.last_processed_file = None

def sync(key):
    global local_storage 
    global _
    if local_storage is None:
        return # Security if local_storage is not ready yet
    try: 
        val = st.session_state[key] #st.session_state.get(key, None) #
    except:
        print("Syncing error for", key, "session state not present")
        return
    if key.startswith("quiz_file_"):
        st.session_state["quiz_file"] = val
        if verbose: print(key, val)
        if val is not None:
            content = val.getvalue()
            compressed = zlib.compress(content)
            encoded = base64.b64encode(compressed).decode()
            file_data = {
                "name": val.name,
                "b64": encoded
            }
            local_storage.setItem("file_package", json.dumps(file_data))
            # Empty the restored object to force use of the new widget
            st.session_state.pop("restored_file", None)
        else:
            # The user clicked on the widget cross
            local_storage.deleteItem("file_package")
            st.session_state.pop("restored_file", None)
    else:
        # Any other widget
        # Use json to store the value
        # print("stored", key, val)
        local_storage.setItem(key, json.dumps(val))

def perform_global_reset():
        global local_storage
        local_storage.deleteAll()
        while len(local_storage.storedItems) > 0:
            time.sleep(0.1)
        st.cache_data.clear()
        st.cache_resource.clear()
        st.session_state.clear()
        st.session_state.uploader_version = int(time.time())
        set_defaults()
        print("Global reset done")
        st.rerun()


@st.cache_data(show_spinner=False)
def adhocReadData(url, secret, autorefresh, button_refresh):
    import time
    if verbose:print("Reading data...")
    time.sleep(0)
    tic = time.perf_counter()
    df, df_filt = readData(url, secret)
    toc = time.perf_counter()
    if verbose: print(f"Reading data execution time: {toc-tic:.3f} seconde(s)")
    return df, df_filt

def generate_cols_from_student(df, dropStudent=False):
    split_cols = df['student'].str.split(r'\s*,\s*', expand=True)
    split_cols.columns = ['name', 'firstname', 'class_group'][:split_cols.shape[1]]
    newdf = pd.concat([split_cols, df], axis=1)
    if dropStudent: newdf = newdf.drop(columns='student')
    return newdf

def recompute_score(adj_bareme, questions, exam_title, df_results, full_df, full_df_filt, quiz, seuil, final_weights, maxtries):
    coeffs = adj_bareme.loc["Coefficient"]
    res_copy = df_results.copy()
    
    if exam_title == "":
        # Scalar product
        res_copy["FinalMark"] = res_copy[questions].dot(coeffs) * (20 / sum(coeffs))
    else:
        # Complete calcul
        res_copy = correctQuizzesDf(
            data=full_df, data_filt=full_df_filt, quiz=quiz, 
            title=exam_title, seuil=seuil, weights=final_weights, 
            bareme=coeffs, maxtries=maxtries
        )
        res_copy["FinalMark"] = res_copy["Note"]
        res_copy.drop(columns='Note', inplace=True, errors='ignore')
        res_copy = generate_cols_from_student(res_copy, dropStudent=False)
    
    return res_copy

def apply_custom_styles():

    custom_css ="""
    <style>
    /* To raise the widget vertically a little (fragile)
    # and reduce vertical space around divider */
    section[data-testid="stSidebar"] div[data-testid="stFileUploader"] {
        margin-top: -0.85rem;
    }
    div[data-testid="stMarkdownContainer"] hr {
        margin-top: 0.3rem;
        margin-bottom: 0.3rem;
    }
    
    /*Remove sidebar header*/

    [data-testid="stLogoSpacer"] {
        display: none;
    }

    [data-testid="stSidebarHeader"] {
        height: auto;
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    
    /* Remove main area header */
    .block-container {
        padding-top: 0rem;
        margin-top: 1rem;
    }
    
    /* don't display streamlit_local_storage iframes */

    /* 1. Target the specific iframe by its title */
    iframe[title="streamlit_local_storage.st_local_storage"] {
        display: none !important;
        height: 0px !important;
        width: 0px !important;
        visibility: hidden !important;
    }

    /* 2. Go back to the parent to delete the reserved space (the slot) */
    div[data-testid="stElementContainer"]:has(iframe[title="streamlit_local_storage.st_local_storage"]) {
        display: none !important;
        margin-bottom: 0px !important;
        padding: 0px !important;
    }
    
    /* 3. Additional Security for Recent Streamlit Versions */
    div.element-container:has(iframe[title="streamlit_local_storage.st_local_storage"]) {
        display: none !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

def main():
    import streamlit as st
    global _
    global local_storage #
    
    # Unique identifier for "tabs"
    if "render_id" not in st.session_state:
        st.session_state.render_id = 0
    st.session_state.render_id += 1

    # This is to stabilize the iframe, in the rendering flow
    storage_container = st.empty()
    with storage_container:
        local_storage = LocalStorage()
    

    old_setItem = local_storage.setItem
    #local_storage.setItem = lambda key, value: old_setItem(key, json.dumps(value), key=key)
    local_storage.setItem = lambda key, value: old_setItem(key, value, key=key+'_'+str(time.time()))
    old_deleteItem = local_storage.deleteItem
    local_storage.deleteItem = lambda key: old_deleteItem(key, key=key+'_'+str(time.time()))

    monitored_parameters = ["selected_lang", "url", "secret", "params_str", "maxtries",
                            "group", "seuil", "exam_title",  "bareme_str"]
    

    if "_init" not in st.session_state:
        # Default values (replace value=...)
        set_defaults()

        # Restore the session state
        for k in monitored_parameters:
            stored = local_storage.getItem(k)
            if verbose: print(k, stored)
            if stored:
                st.session_state[k] = json.loads(stored)
                # print("Restored", k, st.session_state[k])
                pass
        st.session_state["_init"] = True

    
    # --- 3. DYNAMIC FILE RESTORATION LOGIC ---
    # We check whether the widget is empty BUT we have a backup
    
    package_json = local_storage.getItem("file_package")
    #print("file_package", package_json)
    #package_json = False

    if st.session_state.get("quiz_file") is None and package_json:
        # If the restored object is not already in memory, we recreate it
            if "restored_file" not in st.session_state:
                try:
                    package = json.loads(package_json)
                    # On extrait les deux infos du dictionnaire unique
                    raw_bytes = zlib.decompress(base64.b64decode(package["b64"]))
                
                    restored_file = io.BytesIO(raw_bytes)
                    restored_file.name = package["name"] # Le nom est ici !
                    restored_file.size = len(raw_bytes)
                    restored_file.seek(0)
                    st.session_state["restored_file"] = restored_file
                except Exception as e:
                        st.error(f"Restoration error: {e}")
    else:
        # If the widget is filled, we make sure not to use the old restored file
        st.session_state.pop("restored_file", None)
    # -------- End persistence --------------


    # Language selection
    #lang = st.sidebar.selectbox("Language", ["🇬🇧 en", "🇫🇷 fr"], index=["en", "fr"].index(st.session_state.lang))
    languages = {
        "en": "🇬🇧 English",
        "fr": "🇫🇷 Français",
        "es": "🇪🇸 Spanish",
    }

    lang = st.sidebar.selectbox(
        "Language",
        options=list(languages.keys()),
        format_func=lambda x: languages[x],
        index=list(languages.keys()).index(st.session_state.lang),
        key = "selected_lang",
        on_change=sync, args=("selected_lang",)
    )

    if lang != st.session_state.lang:
        print(f"Language changed from {st.session_state.lang} to {lang}")
        _ = set_language(lang)
        #st.rerun()

    

    # --- PAGE CONFIGURATION ---
    st.set_page_config(page_title=_("Dashboard LabQuiz"), layout="wide", 
                    page_icon="src/quiz_dash/1F4CA.png")#"📊")
    
    # Custom styles
    apply_custom_styles()

    parameters_placeholder = st.container()
    group_placeholder = st.container()
    #tabs_placeholder = st.empty()


    # --- SIDEBAR: CONNECTION AND REFRESH RATE ---
    with st.sidebar:
        st.header(_("🔑 Connection"))
        url = st.text_input(_("Google Sheet URL"), placeholder="https://docs.google.com/...", 
                            key="url", on_change=sync, args=("url",))
        secret = st.text_input(_("Secret Key"), type="password", key="secret",
                               on_change=sync, args=("secret",))
        label =_('QUIZ file (YAML) containing corrections')
        st.markdown(
            f"<span style='font-size:0.8rem; color: black;'>{label}</span>",
             unsafe_allow_html=True
            )
        #st.caption(_("QUIZ file (YAML) containing corrections"))
        dynamic_key = f"quiz_file_{st.session_state.uploader_version}"
        uploaded_file = st.file_uploader("label", type=["yaml"], key=dynamic_key, 
                                     label_visibility="collapsed",
                                     #on_change=mark_upload, args=("quiz_file",)
                                     )
        
        if uploaded_file is not None:
            current_file_id = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.last_processed_file != current_file_id:
                for key in st.session_state.keys():
                    if key.startswith("quiz_file"):
                        key_quiz = key
                        break
                sync(key_quiz)
                st.session_state.last_processed_file = current_file_id
        elif uploaded_file is None and st.session_state.last_processed_file is not None:
            # Case where user deletes file manually (red cross)
            st.session_state.last_processed_file = None
       

        quiz_file = uploaded_file if uploaded_file is not None else st.session_state.get("restored_file")
        st.divider()
        
        #st.header(_("⏱️ Monitoring"))
        st.markdown("### ⏱️ " + _("Monitoring"))
        refresh_count = -1

        refresh_min = st.slider(_("Refresh rate (min)"), 1, 30, 10)
        auto_refresh_active = st.checkbox(_("Enable auto-refresh"), value=False)

        if st.button(_("🔄 Refresh now"), use_container_width=True):
            st.session_state.refresh_key += 1

        if auto_refresh_active:
            st.caption(_('Last update: ') + time.strftime('%H:%M:%S'))
            refresh_count = st_autorefresh(
                interval=refresh_min * 60 * 1000,
                key="datarefresh"
            )

        st.divider()

        # Button Reset
        if st.button("🗑️ Global reset", use_container_width=True, on_click=perform_global_reset):
            pass
            #st.session_state["_reset_app"] = True
            #st.rerun()


    # --- MAIN AREA: SETTINGS ---
    with parameters_placeholder:
        st.title(_("📊 Monitoring & Correction Dashboard"))

        with st.expander(_("🛠️ Parameter Configuration (Integrity & Correction)"), expanded=True):
            col_p1, col_p2 = st.columns(2)
            
            with col_p1:
                st.markdown(_("**Monitoring & Source**"))
                params_str = st.text_input(_("Parameters to monitor (e.g.: {'retries':2, 'exam_mode':False, 'test_mode':False})"), 
                                        #value="{'retries':2, 'exam_mode':False, 'test_mode':False}", 
                                        key="params_str", on_change=sync, args=("params_str",))
                maxtries = st.number_input(_("Number of allowed attempts"), min_value=1, 
                                        #value=3, 
                                        key="maxtries", on_change=sync, args=("maxtries",))
                
            with col_p2:
                st.markdown(_("**Grading Algorithm**"))
                seuil = st.number_input(_("Threshold (0 to avoid negative marks)"), 
                                        #value=0.0, 
                                        key="seuil", on_change=sync, args=("seuil",))
                exam_title = st.text_input(_("Exam title (if randomized)"), 
                                        #value="", 
                                        key="exam_title", on_change=sync, args=("exam_title",))

            st.divider()
            col_p3, col_p4 = st.columns(2)
            
            with col_p3:
                st.markdown(_("**Weights Matrix**"))
                # Dictionary editor for base weights
                weights_dict = st.data_editor({
                    _("TP (True Positive)"): 1.0,
                    _("FP (False Positive)"): -1.0,
                    _("FN (False Negative)"): 0.0,
                    _("TN (True Negative)"): 0.0
                }, key="weights_editor",  args=("weights_editor",))
                
                # Conversion for correctQuizzesDf function
                final_weights = {
                    (True, True): weights_dict[_("TP (True Positive)")],
                    (True, False): weights_dict[_("FP (False Positive)")],
                    (False, True): weights_dict[_("FN (False Negative)")],
                    (False, False): weights_dict[_("TN (True Negative)")]
                }

            with col_p4:
                st.markdown(_("**Grading scale per question**"))
                bareme_str = st.text_area(_("Scale dictionary (e.g.: {'q1': 2})"), 
                                        #value="{}", 
                                        key="bareme_str", on_change=sync, args=("bareme_str",)) #key="bareme_str")


    # --- DATA PROCESSING ---

    if url and secret and quiz_file:
        try:
            import copy
            # 1. Reading
            read_error = False
            with st.spinner(_("Reading data...")):
                full_df, full_df_filt = adhocReadData(url, secret, refresh_count, st.session_state.refresh_key)
                if full_df is None or full_df_filt is None:
                    st.error(_("Data could not be read."))
                    read_error = True
            if read_error: st.stop()
            full_df = generate_cols_from_student(full_df, dropStudent=False)
            full_df_filt = generate_cols_from_student(full_df_filt, dropStudent=False)
            # Group selection
            group = _('All')

            if 'class_group' in full_df.columns:
                all_groups = [
                    g for g in full_df['class_group'].unique()
                    if g is not None and not pd.isnull(g)
                ]
                if all_groups:
                    #st.info(_("Select a class or group to monitor."))
                    groups = [ _('All') ] + all_groups
            
                with group_placeholder:
                    cola, colb = st.columns([3, 5])
                    with cola:
                        st.markdown(_("**Class/Group selection**")) 
                        group = st.selectbox(_("Class/Group"), groups, key="group", 
                                             on_change=sync, args=("group",),
                                             label_visibility="collapsed")
                    
                
            # Filtering
            if group == _('All'):
                df, df_filt = full_df, full_df_filt
            else:
                df = full_df.query("class_group == @group")
                df_filt = full_df_filt.query("class_group == @group")                
                #df = full_df.query(f"class_group == '{group}'") 
                #df_filt = full_df_filt.query(f"class_group == '{group}'")
                #print("df_filt:", df_filt )

            # 2. Instantiate a quiz with the quiz file CONTAINING expected values
            
            from labquiz.utils import get_full_object_hash, get_big_integrity_hash
            params = eval(params_str)
            quiz = QuizLab("", quiz_file, needAuthentification=False, mandatoryInternet=False, 
                        in_streamlit=True, **params)              
            wanted_hash = get_full_object_hash(quiz, modules=['main', 'utils'], 
                                                WATCHLIST=['retries', 'exam_mode', 'test_mode'])

            # 3. Global integrity check (hash)
            # wanted_hash = # To be defined! st.secrets["hash"]
            # check_hash_integrity(df, 'full', wanted_hash=wanted_hash) # Will display in terminal or via st if modified
            
            # 4. Students retrieval
            students_raw = sorted(list(df["student"].dropna().unique()))
            students = [s for s in students_raw]
            if "render_id" not in st.session_state:
                st.session_state.render_id = 0
            st.session_state.render_id += 1

            tabs_placeholder = st.empty()
            with tabs_placeholder.container(border=True, key=f"main_frame_{st.session_state.render_id}"): 
                st.empty()
                st.markdown(f"### 🛠️ {_('Live monitoring & Correction')}")
                tab_names = [_("📡 Integrity Live"), _("Monitoring"), _("🎯 Correction & Grades")]
                #selected_tab = st.radio(_("Select a tab"), 
                #                        tab_names, horizontal=True, 
                #                        label_visibility="collapsed",
                #                        key="active_tab")
                #tab_mon, tab_mon_graph, tab_corr = st.tabs(tab_names)
                selected_tab = st.segmented_control(
                    label="Navigation",
                    options=tab_names,
                    default=tab_names[0],
                    key="main_nav_state", 
                    label_visibility="collapsed" 
                )
                st.divider() 
                #with tab_mon:
                if selected_tab == _("📡 Integrity Live"):
                    from labquiz.putils import make_anomalies_df_report, group_anomalies_per_student

                    st.subheader(_("Real-time integrity monitoring"))
                    monitoring_data = [] 
                    
                    # Secure parameters evaluation
                    try:
                        reference = eval(params_str)
                    except Exception as e:
                        p_list = {}
                        st.error(_("Error in parameters format."))
                        print(e)

                    includeRAS = True
                    if st.checkbox(_("Also use full hash"), value=False, 
                                help=_("Use the full hash of the source code, live object and parameters")):
                        reference['full_hash'] = wanted_hash
                    if st.checkbox(_("Only display anomalies"), value=False, 
                                help=_("Display anomalies only, or full report")):
                        includeRAS = False

                    Tab_report = make_anomalies_df_report(df, reference, ignore_keys=[], 
                                                        includeRAS=includeRAS)

                    if st.checkbox(_("Collect anomalies per student"), value=False, 
                                help=_("Group anomalies per student")):
                        Grouped_tab_report = group_anomalies_per_student(Tab_report)
                        if not Grouped_tab_report.empty:
                            st.dataframe(Grouped_tab_report, width='stretch', hide_index=True)
                        else:
                            st.info(_("No anomalies found at all."))
                    else:
                        st.dataframe(Tab_report, width='stretch', hide_index=True)

                elif selected_tab == _("Monitoring"): 
                #with tab_mon_graph:
                    st.subheader(_("Activity monitoring"))
                    
                    df = df.copy()
                    df.loc[:, "has_seen_correction"] = (
                        df["event_type"].eq("correction")
                        .groupby([df["student"], df["quiz_title"]])
                        .transform("cummax")
                    ).fillna(False).astype(bool)


                    df_last = (
                        df.query("(event_type == 'validate' or event_type == 'validate_exam') and not has_seen_correction", engine="python")
                        .groupby(["student", "quiz_title"], as_index=False)
                        .tail(1)[["student", "quiz_title"]]
                    )

                    def tronqLabels(labels, K=10):
                        return [cat[:K] + '..' if (isinstance(cat, str) and (len(cat) > K)) else cat for cat in labels]

                    ## Number of unique quizzes completed per student  ###
                    def plot_quiz_counts(ax): 
                        quiz_count_by_student = (
                            df_last.groupby("student")["quiz_title"]
                                .apply(len)
                                .sort_index(ascending=False)
                        )
                        ax.barh(tronqLabels(quiz_count_by_student.index), quiz_count_by_student.values, height=0.95)
                        ax.set_title(_("Number of quizzes completed"))
                        
                    ### Obtained scores #########
                    def plot_score_by_student(ax): 
                        score_by_student = (
                            df_last.groupby("student")["score"]
                                .apply(np.sum)
                                .sort_index(ascending=False)
                        )

                        ax.barh(tronqLabels(score_by_student.index), score_by_student.values, height=0.95)
                        ax.set_title(_("Obtained score"))

                        
                    ### Quizzes completed by the class #########
                    def plot_class_results(ax):    
                        counts = (
                            df_last["quiz_title"]
                            .value_counts()
                            .sort_index(
                                key=lambda idx: idx.str.extract(r"(\d+)").astype(int)[0]
                            )   # alphabetical order
                        )
                        ax.barh(counts.index, counts.values, height=0.95)
                        ax.set_title(_("Quizzes completed by the group"))

                    def update_output(plotting_func):
                            fig, ax = plt.subplots(figsize=(5, 4), constrained_layout=True) 
                            plotting_func(ax)
                            ax.tick_params(axis='y', labelsize=8)
                            fig.set_tight_layout(True)
                            st.pyplot(fig)
                    
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        st.subheader(_("Number of quizzes per student"))
                        update_output(plot_quiz_counts)

                    with col_p2:                
                        st.subheader(_("Quizzes completed - whole class"))
                        update_output(plot_class_results)
                    
                    quiz_count_by_student = (
                    df_last.groupby("student")["quiz_title"]
                        .agg(
                            nb="size",
                            quizzes_list=list,
                            )
                        .sort_index(ascending=True)
                    )

                    st.markdown(_("#### Number of individual quizzes"))
                    #quiz_count_by_student["nb"] = quiz_count_by_student["nb"].astype(int)

                    quiz_count_by_student = quiz_count_by_student.reset_index().rename(columns={"index": "student"})
                    quiz_count_by_student['student'] = quiz_count_by_student['student'].apply(
                        lambda x: x.split(',')[0].strip().upper() + ' ' + x.split(',')[1].strip().title() 
                        if len(x.split(',')) > 1 else x
                    )
                    st.dataframe(quiz_count_by_student, 
                            column_config={
                            'student': st.column_config.TextColumn(width='medium'),
                            'nb': st.column_config.NumberColumn(
                                width="auto",
                                format="%d"  
                            ),
                            'quizzes_list': st.column_config.TextColumn(width='auto')
                            }
                        )
                elif selected_tab == _("🎯 Correction & Grades"):
                #with tab_corr:
                    st.subheader(_("Correction & Grades"))
                    col_res1, col_res2 = st.columns([99, 1])
                    b_dict = {}
                    with col_res1:    
                        st.caption(_('Last update of corrections (before auto-refresh): ') + f"{st.session_state.last_correction_update}")
                        if st.button(_("🚀 Launch full correction"), width='stretch'):
                            st.session_state.last_correction_update = time.strftime('%H:%M:%S')
                            st.caption(_('Last update of corrections: ') + f"{st.session_state.last_correction_update}")
                            with st.spinner(_("Calculating scores per question...")):
                                try:
                                    b_dict = eval(bareme_str)              
                                except:
                                    b_dict = {}
                                
                                st.session_state.df_results = correctQuizzesDf(
                                    data=full_df, 
                                    data_filt=full_df_filt, 
                                    quiz=quiz, 
                                    title=exam_title if exam_title != "" else None, 
                                    seuil=seuil, 
                                    weights=final_weights, 
                                    bareme=b_dict, 
                                    maxtries=maxtries
                                )
                                st.session_state.df_results = st.session_state.df_results.reset_index().rename(columns={"index": "student"})
                                st.session_state.df_results = generate_cols_from_student(st.session_state.df_results, dropStudent=True)
                                st.session_state.df_results.drop(columns='Note', inplace=True, errors='ignore')
                                st.session_state.df_results.drop(columns='maxpts', inplace=True, errors='ignore')
                                
                                if exam_title == "":
                                    st.session_state.df_results.drop(columns='Note', inplace=True, errors='ignore')
                                st.success(_("Scores calculated!"))
                        
                                questions = [c for c in st.session_state.df_results.columns if c not in [
                                    "student", "maxpts", "Note", "FinalMark", 'name', 'firstname', 'class_group']
                                    ]                    
                                st.session_state.coeffs = {q: float(b_dict.get(q, 1.0)) for q in questions}  
                    
                            st.session_state.df_final = st.session_state.df_results.copy() # All groups in df_final
                        
                            
                        if st.session_state.df_final is not None:

                            if group != _("All"):
                                st.session_state.df_results = st.session_state.df_final.query("class_group == @group")
                            else:
                                st.session_state.df_results = st.session_state.df_final
                            st.session_state.show_scores = True
                                
                            st.markdown(_("#### ⚖️ Adjust Scale"))
                            questions = [c for c in st.session_state.df_results.columns if c not in ["student", "maxpts", "Note", "FinalMark", 'name', 'firstname', 'class_group']]
                            
                            # Create a mini-table to adjust weights without recalculating everything
                            adj_bareme = st.data_editor(
                                pd.DataFrame({ "AvgScore": st.session_state.df_results[questions].mean(axis=0), 
                                            "Coefficient": st.session_state.coeffs.values()},
                                            ).transpose(),
                                hide_index=False,
                                width='stretch',
                            )

                            st.session_state.df_results = recompute_score(
                                adj_bareme, 
                                questions, 
                                exam_title, 
                                st.session_state.df_results, 
                                full_df, 
                                full_df_filt, 
                                quiz, 
                                seuil, 
                                final_weights, 
                                maxtries
                            )
                            st.session_state.show_scores = True

                            avg_note = st.session_state.df_results["FinalMark"].mean()
                            std_note = st.session_state.df_results["FinalMark"].std()
                            st.markdown(_("#### Grades Table"))
                            st.caption(_('Average: ') + f"{avg_note:.2f} / 20. " + _('Standard deviation: ') + f"{std_note:.2f}")
                            if group != _("All"):
                                coeffs = adj_bareme.loc["Coefficient"]
                                st.session_state.df_final["FinalMark"] = st.session_state.df_final[questions].dot(coeffs)*(20/sum(coeffs))
                                full_avg_note = st.session_state.df_final["FinalMark"].mean()
                                full_std_note = st.session_state.df_final["FinalMark"].std()
                                st.caption(_('Class: ') + _('Average: ') + f"{full_avg_note:.2f} / 20. " + _('Standard deviation: ') + f"{full_std_note:.2f}")
                            
                            st.dataframe(st.session_state.df_results, width='stretch')
                            
                            st.session_state.show_scores = False 
                        elif st.session_state.df_results is not None:
                            st.info(_("Scores per question available. Click Recalculate to see final marks."))
                        else:
                            st.caption(_("Waiting for correction to start."))

        except Exception as e:
            st.error(_('Error during reading or processing: ') + f"{e}")
    else:
        st.warning(_("Please enter URL and SECRET in the sidebar, and load a quiz file."))

if __name__ == "__main__":
    main()