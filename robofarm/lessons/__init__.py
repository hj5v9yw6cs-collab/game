"""Все главы игры по порядку."""

from robofarm.lessons import chapter1, chapter2, chapter3, chapter4, chapter5, chapter6, chapter7

CHAPTERS = [chapter1.CHAPTER, chapter2.CHAPTER, chapter3.CHAPTER, chapter4.CHAPTER,
            chapter5.CHAPTER, chapter6.CHAPTER, chapter7.CHAPTER]
LESSONS = [lesson for ch in CHAPTERS for lesson in ch.lessons]


def chapter_of(lesson):
    return next(ch for ch in CHAPTERS if lesson in ch.lessons)


def first_lesson_index(chapter):
    return LESSONS.index(chapter.lessons[0])
