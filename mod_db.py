DB_NAME = "student_logs.db"

import os 
import sqlite3

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()


q = 'UPDATE CLASSES_STUDENTS SET teach_assn="AC/MH" WHERE teach_assn="Orange"'

ORDER BY name;"""

cur.execute(q)
    