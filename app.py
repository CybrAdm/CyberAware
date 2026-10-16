import streamlit as st

from auth.users import (
    get_current_role,
    get_current_user,
    is_authenticated,
    logout_session,
    restore_session,
)
from services.startup import prepare_data
from ui.pages import (
    board,
    home,
    learn,
    login,
    mine,
    quiz,
    register,
    report,
    review,
    user_board,
)


st.set_page_config(page_title="CyberAware", page_icon="CA", layout="wide")
prepare_data()
restore_session()

if is_authenticated():
    user = get_current_user()
    st.sidebar.write(user["username"])
    st.sidebar.write("Role: " + user["role"])
    if st.sidebar.button("Log out"):
        logout_session()
        st.rerun()

if not is_authenticated():
    pages = [
        st.Page(login, title="Login", default=True),
        st.Page(register, title="Register"),
    ]
elif get_current_role() == "admin":
    pages = [
        st.Page(home, title="Home", default=True),
        st.Page(report, title="Report"),
        st.Page(mine, title="My reports"),
        st.Page(review, title="Review"),
        st.Page(learn, title="Awareness"),
        st.Page(quiz, title="Quiz"),
        st.Page(board, title="Dashboard"),
    ]
else:
    pages = [
        st.Page(home, title="Home", default=True),
        st.Page(report, title="Report"),
        st.Page(mine, title="My reports"),
        st.Page(learn, title="Awareness"),
        st.Page(quiz, title="Quiz"),
        st.Page(user_board, title="Dashboard"),
    ]

st.navigation(pages).run()
