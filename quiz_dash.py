import streamlit as st
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh
import matplotlib.pyplot as plt
# Import des fonctions labquiz
from labquiz.main import QuizLab
from labquiz.putils import (
    readData, 
    check_integrity_msg, 
    check_hash_integrity, 
    correctQuizzesDf
)

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Dashboard LabQuiz", layout="wide", 
                   page_icon="1F4CA.png")#"📊")

# --- INITIALISATION DU SESSION STATE ---
if "df_results" not in st.session_state:
    st.session_state.df_results = None
if "df_final" not in st.session_state:
    st.session_state.df_final = None
st.session_state.show_scores = False
if "last_correction_update" not in st.session_state:
    st.session_state.last_correction_update = None


# --- SIDEBAR : CONNEXION ET RYTHME ---
with st.sidebar:
    st.header("🔑 Connexion")
    url = st.text_input("URL Google Sheet", placeholder="https://docs.google.com/...", key="url")
    secret = st.text_input("Secret Key", type="password", key="secret")
    quiz_file = st.file_uploader("Fichier QUIZ (YAML) contenant les corrections", type=["yaml"], key="quiz_file")
    st.divider()
    
    st.header("⏱️ Monitoring")
    refresh_min = st.slider("Rythme d'actualisation (min)", 1, 30, 10)
    auto_refresh_active = st.checkbox("Activer l'auto-refresh", value=False)
    
    if auto_refresh_active:
        # Déclenche un rerun automatique du script
        st.caption(f"Dernière mise à jour : {time.strftime('%H:%M:%S')}")
        st_autorefresh(interval=refresh_min * 60 * 1000, key="datarefresh")

# --- ZONE PRINCIPALE : PARAMÉTRAGE ---
st.title("📊 Dashboard de Suivi & Correction")

with st.expander("🛠️ Configuration des Paramètres (Intégrité & Correction)", expanded=True):
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.markdown("**Surveillance & Source**")
        params_str = st.text_input("Paramètres à surveiller (ex:  {'retries':2, 'exam_mode':True, 'test_mode':False})", value="{}", key="params_str")
        #st.text_input("Nom du fichier QUIZ (YAML)", value="quiz.yaml")
        maxtries = st.number_input("Nombre d'essais autorisés", min_value=1, value=1, key="maxtries")
        
    with col_p2:
        st.markdown("**Algorithme de Notation**")
        seuil = st.number_input("Seuil (0 pour éviter les notes négatives)", value=0.0, key="seuil")
        exam_title = st.text_input("Titre de l'examen (si tirage au sort)", value="", key="exam_title")

    st.divider()
    col_p3, col_p4 = st.columns(2)
    
    with col_p3:
        st.markdown("**Matrice de poids (Weights)**")
        # Éditeur de dictionnaire pour les poids de base
        weights_dict = st.data_editor({
            "VP (Vrai Positif)": 1.0,
            "FP (Faux Positif)": -1.0,
            "FN (Faux Négatif)": 0.0,
            "VN (Vrai Négatif)": 0.0
        }, key="weights_editor")
        
        # Conversion pour la fonction correctQuizzesDf
        final_weights = {
            (True, True): weights_dict["VP (Vrai Positif)"],
            (True, False): weights_dict["FP (Faux Positif)"],
            (False, True): weights_dict["FN (Faux Négatif)"],
            (False, False): weights_dict["VN (Vrai Négatif)"]
        }

    with col_p4:
        st.markdown("**Barème par question**")
        bareme_str = st.text_area("Dictionnaire de barème (ex: {'q1': 2})", value="{}", key="bareme_str")

# --- TRAITEMENT DES DONNÉES ---
if url and secret and quiz_file:
    try:
        import copy
        # 1. Lecture
        df, df_filt = readData(url, secret)
        # 2. Instancier un quiz avec le fichier de quiz CONTENANT les valeurs attendues
         
        from labquiz.utils import get_full_object_hash, get_big_integrity_hash
        params = eval(params_str)
        quiz = QuizLab("", quiz_file, needAuthentification=False, mandatoryInternet=False, 
                       in_streamlit=True, **params)              
        wanted_hash = get_full_object_hash(quiz, modules=['main', 'utils'], 
                                             WATCHLIST=['retries', 'exam_mode', 'test_mode'])


        # 3. Vérification d'intégrité globale (hash)
        # wanted_hash = # A définir ! st.secrets["hash"]
        #check_hash_integrity(df, 'full', wanted_hash=wanted_hash) # Affichera dans le terminal ou via st si modifiée
        
        # 4. Récupération des étudiants
        students_raw = sorted(list(df["student"].dropna().unique()))
        students = [s.title() for s in students_raw]

        # --- ONGLETS ---
        tab_mon, tab_mon_graph, tab_corr = st.tabs(["📡 Integrity Live", "Monitoring", "🎯 Correction & Notes"])

        with tab_mon:
            from labquiz.putils import make_anomalies_df_report, group_anomalies_per_student

            st.subheader("Suivi de l'intégrité en temps réel")
            monitoring_data = [] 
            
            # Évaluation sécurisée des paramètres
            try:
                reference = eval(params_str)
            except Exception as e:
                p_list = {}
                st.error("Erreur dans le format des paramètres.")
                print(e)

            includeRAS = True
            if st.checkbox("Also use full hash", value=False, 
                           help="Use the full hash of the source code, live object and parameters"):
                reference['full_hash'] = wanted_hash
            if st.checkbox("Only display anomalies", value=False, 
                           help="Display anomalies only, or full report"):
                includeRAS = False

            #print("reference", reference) 

            zoup ='''for s in students_raw:
                try:
                    is_ok, msg = check_integrity_msg(s, p_list, df)
                except Exception as e:
                    print(e)
                    print("is_ok, msg:", is_ok, msg)

                if not is_ok:  # Only display anomalies
                    monitoring_data.append({
                        "Étudiant": s.title(),
                        "Status": "✅" if is_ok else "⚠️ Anomalie",
                        "Détails": msg if msg else "RAS"
                    })'''
            
            Tab_report = make_anomalies_df_report(df, reference, ignore_keys=[], 
                                                  includeRAS=includeRAS)

            if st.checkbox("Collect anomalies per student", value=False, 
                           help="Group anomalies per student"):
                Grouped_tab_report = group_anomalies_per_student(Tab_report)
                if not Grouped_tab_report.empty:
                    st.dataframe(Grouped_tab_report, width='stretch', hide_index=True)
                else:
                    st.info("No anomalies found at all.")
            else:
            #st.dataframe(pd.DataFrame(monitoring_data), width='stretch', hide_index=True)
                st.dataframe(Tab_report, width='stretch', hide_index=True)

        with tab_mon_graph:
            st.subheader("Monitoring de l'activité")
            

            df["has_seen_correction"] = (
                df["event_type"].eq("correction")
                .groupby([df["student"], df["quiz_title"]])
                .transform("cummax")
            ).fillna(False).astype(bool)


            df_last = (
                df.query("(event_type == 'validate' or event_type == 'validate_exam') and not has_seen_correction", engine="python")
                .groupby(["student", "quiz_title"], as_index=False)
                .tail(1)[["student", "quiz_title"]]
            )

            old = '''df_last = df.query("event_type == 'validate' or event_type == 'validate_exam' ").drop_duplicates(
                subset=["student", "quiz_title", 'event_type'],
                keep="last"
            )'''

            #df_last = df_last.query("event_type == 'validate' ")
            #print("df_last", df_last['student'].unique)

            def tronqLabels(labels, K=10):
                return [cat[:K] + '..' if (isinstance(cat, str) and (len(cat) > K)) else cat for cat in labels]

            ## Nombre de quizzes uniques réalisés par étudiant  ###
            def plot_quiz_counts(ax): 
                quiz_count_by_student = (
                    df_last.groupby("student")["quiz_title"]
                        .apply(len)
                        .sort_index(ascending=False)
                )
                ax.barh(tronqLabels(quiz_count_by_student.index), quiz_count_by_student.values, height=0.95)
                ax.set_title("Nombre de quizzes réalisés")
                
            ### Scores obtenus #########
            def plot_score_by_student(ax): 
                score_by_student = (
                    df_last.groupby("student")["score"]
                        .apply(np.sum)
                        .sort_index(ascending=False)
                )

                ax.barh(tronqLabels(score_by_student.index), score_by_student.values, height=0.95)
                ax.set_title("Score obtenu")

                
            ### Quiz réalisés par la classe #########
            def plot_class_results(ax):    
                counts = (
                    df_last["quiz_title"]
                    .value_counts()
                    .sort_index(
                        key=lambda idx: idx.str.extract(r"(\d+)").astype(int)[0]
                    )   # ordre alphabétique
                )
                ax.barh(counts.index, counts.values, height=0.95)
                ax.set_title("Quizzes réalisés par le groupe")

            def update_output(plotting_func):
                    fig, ax = plt.subplots(figsize=(5, 4), constrained_layout=True) 
                    plotting_func(ax)
                    ax.tick_params(axis='y', labelsize=8)
                    fig.set_tight_layout(True)
                    st.pyplot(fig)
                    #plt.show()        
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.subheader("Nombre de quizzes par étudiant")
                update_output(plot_quiz_counts)

            with col_p2:                
                st.subheader("Nb quizzes classe complète")
                update_output(plot_class_results)
            
            quiz_count_by_student = (
            df_last.groupby("student")["quiz_title"]
                .agg(
                    nb="size",
                    quizzes_list=list,
                    )
                .sort_index(ascending=True)
            )

            st.markdown("#### Nombre de quizzes individuels")
            st.dataframe(quiz_count_by_student, 
                    column_config={
                    'student': st.column_config.TextColumn(width='medium'),
                    'nb': st.column_config.TextColumn(width='small'),
                    'quizzes_list': st.column_config.TextColumn(width='medium')
                    }
                )

        with tab_corr:
            st.subheader("Correction & Notes")
            col_res1, col_res2 = st.columns([99, 1])
            b_dict = {}
            with col_res1:    
                st.caption(f"Dernière mise à jour des corrections (avant auto-refresh) : {st.session_state.last_correction_update}")
                if st.button("🚀 Lancer la correction complète", width='stretch'):
                    st.session_state.last_correction_update = time.strftime('%H:%M:%S')
                    st.caption(f"Dernière mise à jour des corrections : {st.session_state.last_correction_update}")
                    with st.spinner("Calcul des scores par question..."):
                        try:
                            b_dict = eval(bareme_str)              
                        except:
                            b_dict = {}
                        
                        st.session_state.df_results = correctQuizzesDf(
                            data=df, 
                            data_filt=df_filt, 
                            quiz=quiz, 
                            title=exam_title if exam_title != "" else None, 
                            seuil=seuil, 
                            weights=final_weights, 
                            bareme=b_dict, 
                            maxtries=maxtries
                        )
                        st.session_state.df_results.drop(columns='maxpts', inplace=True, errors='ignore')
                        st.success("Scores calculés !")
                
                        questions = [c for c in st.session_state.df_results.columns if c not in ["student", "maxpts","FinalMark"]]                    
                        st.session_state.coeffs = {q: float(b_dict.get(q, 1.0)) for q in questions}  
              
                st.session_state.df_final = st.session_state.df_results
                st.session_state.show_scores = True

                if st.session_state.df_results is not None:
                    #st.divider()
                    def recompute_score():
                        coeffs = adj_bareme.loc["Coefficient"] #dict
                        res_copy = st.session_state.df_results.copy()
                        if exam_title == "":
                            res_copy["FinalMark"] = res_copy[questions].dot(coeffs)*(20/sum(coeffs))
                        else:
                            res_copy = correctQuizzesDf(data=df, data_filt=df_filt, quiz=quiz, 
                                    title=exam_title, seuil=seuil, weights=final_weights, 
                                    bareme=coeffs, maxtries=maxtries)
                        st.session_state.df_final = res_copy
                        st.session_state.show_scores = True
                    

                if st.session_state.df_final is not None:
                    
                    st.markdown("#### ⚖️ Ajuster le Barème")
                    questions = [c for c in st.session_state.df_results.columns if c not in ["student", "maxpts","FinalMark"]]
                    
                    # Création d'un mini-tableau pour ajuster les poids sans tout recalculer

                    adj_bareme = st.data_editor(
                        pd.DataFrame({ "AvgScore": st.session_state.df_results[questions].mean(axis=0), 
                                       "Coefficient": st.session_state.coeffs.values()},
                                      ).transpose(),
                        hide_index=False,
                        width='stretch',
                    )

                    recompute_score()

                    avg_note = st.session_state.df_final["FinalMark"].mean()
                    std_note = st.session_state.df_final["FinalMark"].std()
                    st.markdown("#### Tableau des Notes")
                    st.caption(f"Moyenne : {avg_note:.2f} / 20. Ecart-type : {std_note:.2f}")

                    st.dataframe(st.session_state.df_final, width='stretch')
                    
                    st.session_state.show_scores = False 
                elif st.session_state.df_results is not None:
                    st.info("Scores par question disponibles. Cliquez sur Recalculer pour voir les notes finales.")
                else:
                    st.caption("En attente du lancement de la correction.")
                

    except Exception as e:
        st.error(f"Erreur lors de la lecture ou du traitement : {e}")
else:
    st.warning("Veuillez renseigner URL et SECRET dans la barre latérale, " \
    "et charger un fichier de quiz.")