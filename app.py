from datetime import date
from random import choice
from statistics import mean
import sqlite3

import streamlit as st
from pathlib import Path

import db

st.set_page_config(page_title="Що подивитися?", page_icon="🎬", layout="centered")


def catalogue():
    st.title("Що подивитися?")
    rows = db.titles()
    scores = [r["rating"] for r in rows if r["rating"] is not None]
    a, b, c = st.columns(3)
    a.metric("У списку", len(rows))
    b.metric("Переглянуто", sum(r["status"] == db.STATES[2] for r in rows))
    c.metric("Середня оцінка", f"{mean(scores):.1f} / 10" if scores else "—")
    query = st.text_input("Пошук за назвою", placeholder="Наприклад, Інтерстеллар")
    a, b = st.columns(2)
    genres = db.genres()
    genre = a.selectbox("Жанр", ["Усі жанри", *genres])
    status = b.selectbox("Статус", ["Усі статуси", *db.STATES])
    found = db.titles(query, genres.get(genre), None if status == "Усі статуси" else status)
    st.subheader(f"Каталог · {len(found)}")
    if not found:
        st.info("Записів за цими умовами немає.")
        return
    st.dataframe([{"Назва": r["name"], "Рік": str(r["year"]), "Формат": r["kind"],
                   "Жанр": r["genre"], "Статус": r["status"],
                   "Оцінка": str(r["rating"]) if r["rating"] else "—"} for r in found],
                 hide_index=True, width="stretch")


def manage():
    st.title("Керування списком")
    if message := st.session_state.pop("notice", None):
        st.success(message)
    mode = st.radio("Операція", ["Додати", "Редагувати", "Видалити"], horizontal=True)
    genres = db.genres()
    entry = {}
    if mode != "Додати":
        records = {r["id"]: r for r in db.titles()}
        if not records:
            st.info("Список порожній. Спочатку додайте запис.")
            return
        def label(i):
            r = records[i]
            return f"{r['name']} ({r['year']}, {r['kind']})"
        chosen = st.selectbox("Запис", list(records), format_func=label)
        entry = records[chosen]

    if mode == "Видалити":
        confirmed = st.checkbox(f"Підтверджую видалення «{entry['name']}»", key=f"confirm_{chosen}")
        if st.button("Видалити запис", disabled=not confirmed):
            db.remove(chosen)
            st.session_state.notice = f"Видалено «{entry['name']}»."
            st.rerun()
        return

    with st.form(f"entry_{entry.get('id', 'new')}"):
        name = st.text_input("Назва", entry.get("name", ""), max_chars=120)
        a, b = st.columns(2)
        year = a.number_input("Рік виходу", 1888, date.today().year + 1,
                              entry.get("year", date.today().year))
        kind = b.selectbox("Формат", db.FORMATS, index=db.FORMATS.index(entry.get("kind", db.FORMATS[0])))
        genre = st.selectbox("Жанр", list(genres),
                             index=list(genres).index(entry.get("genre", next(iter(genres)))))
        a, b = st.columns(2)
        status = a.selectbox("Статус", db.STATES, index=db.STATES.index(entry.get("status", db.STATES[0])))
        rating = b.selectbox("Оцінка після перегляду", [None, *range(1, 11)],
                             index=entry.get("rating") or 0, format_func=lambda n: "Без оцінки" if n is None else str(n))
        if st.form_submit_button("Зберегти запис", type="primary"):
            db.save(name, year, kind, genres[genre], status, rating, entry.get("id"))
            st.session_state.notice = f"Збережено «{name.strip()}»."
            st.rerun()


def author():
    st.title("Про автора")
    st.subheader("Смірнов Едуард")
    st.write("Група П-31 · Гусятинський фаховий коледж")
    st.image(str(Path(__file__).with_name('assets') / 'author.jpg'), width=180)
    st.write("«Мій кінозал» починається з простого запитання: що подивитися сьогодні з того, що друзі радили ще минулого тижня?")
    st.caption("Python · Streamlit · SQLite. Демонстраційний каталог спільний для відвідувачів цього екземпляра.")

    st.divider()
    st.subheader("Вибір на вечір")
    planned = db.titles(status=db.STATES[0])
    if not planned:
        st.info("Список планів порожній. Додайте фільм або серіал зі статусом «Хочу подивитися».")
        return
    genre = st.selectbox("Що хочеться подивитися?", ["Будь-який жанр", *sorted({item["genre"] for item in planned})])
    if genre != "Будь-який жанр":
        planned = [item for item in planned if item["genre"] == genre]
    previous = st.session_state.get("evening_id")
    if st.button("Підібрати на вечір"):
        alternatives = [item for item in planned if item["id"] != previous]
        st.session_state.evening_id = choice(alternatives or planned)["id"]
    selected = next((item for item in planned if item["id"] == st.session_state.get("evening_id")), None)
    if selected:
        with st.container(border=True):
            st.text(selected["name"])
            st.caption(f"{selected['kind']} · {selected['year']} · {selected['genre']}")


page = st.navigation({
    "Мій кінозал": [
        st.Page(catalogue, title="Каталог", default=True),
        st.Page(manage, title="Керування списком", url_path="manage"),
        st.Page(author, title="Про автора", url_path="author"),
    ]
})
try:
    db.initialize()
    page.run()
except ValueError as exc:
    st.error(str(exc))
except sqlite3.Error:
    st.error("Не вдалося виконати операцію з базою даних. Перевірте доступ до файла й повторіть спробу.")
