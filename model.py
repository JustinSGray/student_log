import sqlite3
            
def _get_last_id(): 
    query = "SELECT last_insert_rowid()"
    return cur.execute(query).fetchone()[0]

def insert_class(name): 
    query = """INSERT INTO CLASSES (class_id,name) VALUES(Null,?)"""
    cur.execute(query,(name,))
    conn.commit()
    return _get_last_id()
    
    
def del_class(class_id):
    if isinstance(class_id,list) or isinstance(class_id,tuple): 
        query="DELETE FROM CLASSES WHERE class_id IN (:id)"
        cur.executemany(query,[{'id':x} for x in class_id])
    else: 
        query="DELETE FROM CLASSES WHERE class_id=?"
        cur.execute(query,(class_id,))    
    conn.commit()
    return True
    
def insert_student( student_id,first_name,last_name,dec,parent_name,
                    parent_email,DOB,grade,phone_number,r_score_in,
                    w_score_in,r_score_out,w_score_out,notes=None): 
    
    query="INSERT INTO STUDENTS VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    
    cur.execute(query,(student_id,first_name,last_name,dec,parent_name,
    parent_email,DOB,grade,phone_number,r_score_in,w_score_in,
    r_score_out,w_score_out,notes))
    
    conn.commit()
    return _get_last_id()    
    
def del_student(student_id):
    if isinstance(student_id,list) or isinstance(student_id,tuple): 
        query="DELETE FROM STUDENTS WHERE student_id IN (:id)"
        cur.executemany(query,[{'id':x} for x in student_id])
    else: 
        query="DELETE FROM STUDENTS WHERE student_id=?"
        cur.execute(query,(student_id,))
    
    conn.commit()
    return True
    
def insert_proctor(_class,student):
    query = """INSERT INTO PROCTOR (class_id,student_id) VALUES(?,?)"""
    cur.execute(query,(_class,student))
    conn.commit()
    return True
    
def insert_record(_class,student,notes=None):
    query='''INSERT INTO RECORDS (class_id,student_id,notes,datetime) 
    VALUES(?,?,?,datetime('now'))'''
    cur.execute(query,(_class,student,notes))
    conn.commit()
    return True
    
def link_class_student(_class,student): 
    #check if student exists
    query = "SELECT student_id FROM STUDENTS WHERE student_id=?"
    student_id = cur.execute(query,(student,)).fetchone()
    #check if class exists
    query = "SELECT class_id FROM CLASSES WHERE class_id=?"
    class_id = cur.execute(query,(_class,)).fetchone()
    
    # if both exists, check to see if that relation already exists
    query = """SELECT * FROM CLASSES_STUDENTS WHERE (class_id=? 
    and student_id=?)"""
    if not cur.execute(query,(_class,student)).fetchone() and student_id \
        and class_id:
        query = 'INSERT INTO CLASSES_STUDENTS VALUES(?,?,"ENR","GenEd")'
        cur.execute(query,(class_id[0],student_id[0]))
        #commit
        conn.commit()
        return True
    
    return False   
        
     

if __name__=="__main__":
    DB_NAME = "student_logs.db"

    import os 
    if os.path.isfile(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Create tables
    cur.execute('''create table STUDENTS(student_id INTEGER PRIMARY KEY, 
    first_name VARCHAR(50), last_name VARCHAR(50),dec BOOLEAN DEFAULT 0, 
    parent_name VARCHAR(60), parent_email VARCHAR(100), DOB VARCHAR(20), 
    grade INTEGER, phone_number VARCHAR(10), 
    r_score_in INTEGER, w_score_in INTEGER, 
    r_score_out INTEGER,w_score_out INTEGER, notes TEXT DEFAULT NULL)''')
    
    cur.execute("""create table CLASSES(class_id INTEGER PRIMARY KEY, 
    name VARCHAR(20), active BOOLEAN DEFAULT 0, date DATE)""")
    
    cur.execute('''create table PROCTOR( q1 BOOLEAN DEFAULT 0,
    q2 BOOLEAN DEFAULT 0, student_id INTEGER, class_id INTEGER,
    FOREIGN KEY(student_id) REFERENCES STUDENTS(student_id),
    FOREIGN KEY(class_id) REFERENCES CLASSES(class_id),
    PRIMARY KEY (class_id, student_id) )''')
    
    cur.execute('''create table RECORDS(record_id INTEGER PRIMARY KEY,
    datetime DATETIME, notes TEXT, student_id INTEGER, class_id INTEGER,
    FOREIGN KEY(student_id) REFERENCES  STUDENTS(student_id),
    FOREIGN KEY(class_id)   REFERENCES  CLASSES(class_id))''')
    
    #on delete cascade
    cur.execute('''CREATE TRIGGER student_cascade_delete
    BEFORE DELETE
    ON STUDENTS
    FOR EACH ROW
    BEGIN
        DELETE FROM RECORDS WHERE RECORDS.student_id = old.student_id;
        DELETE FROM PROCTOR WHERE PROCTOR.student_id = old.student_id;
        DELETE FROM CLASSES_STUDENTS WHERE 
            CLASSES_STUDENTS.student_id = old.student_id;
    END''')
    
    cur.execute('''CREATE TRIGGER class_cascade_delete
    BEFORE DELETE
    ON CLASSES
    FOR EACH ROW
    BEGIN
        DELETE FROM RECORDS WHERE RECORDS.class_id = old.class_id;
        DELETE FROM PROCTOR WHERE PROCTOR.class_id = old.class_id;
        DELETE FROM CLASSES_STUDENTS WHERE 
            CLASSES_STUDENTS.class_id = old.class_id;
    END''')

    
    #CLASSES to STUDENTS many-to-many link table
    cur.execute('''create table CLASSES_STUDENTS(
    class_id NOT NULL, student_id NOT NULL , 
    status VARCHAR(4) DEFAULT "ENR",
    teach_assn VARCHAR(5) DEFAULT "GenEd",
    PRIMARY KEY (class_id, student_id))''')
    
    # for every class_student link, make a new proctor entry
    cur.execute("""CREATE TRIGGER class_student_create_proctor
    AFTER INSERT on CLASSES_STUDENTS
    FOR EACH ROW
    BEGIN
        INSERT INTO PROCTOR (class_id,student_id) 
        VALUES(new.class_id,new.student_id);
    END
    """) 
    
    conn.commit()




    
    """
        #set up some dummy data
        args = ('167735','Brittany Lynn','Caudill',0,'Kays, Tammy',
                'TLK167736@parents.ecotoh.org','10--27-1990',12,
                '(419) 619-8426 [cell]',364,407,'Null','Null')    
        insert_student(*args)
        
        args = ('108084','Samantha','Anderson',0,'McCabe, Rhonda',
                'RM108083@parents.ecotoh.org','3-1-1993',11,
                '(614) 554-7970',395,403,'Null','Null',"something about mary")
        insert_student(*args)
        
        args = ('108085','Samantha','Anderson',0,'McCabe, Rhonda',
                'RM108083@parents.ecotoh.org','3-1-1993',11,
                '(614) 554-7970',395,403,'Null','Null')
        insert_student(*args)
        
        insert_class('some class')
        insert_class('some other class')
        insert_class('a third class')
        
        print link_class_student('1','108084')
        for row in cur.execute("SELECT * from PROCTOR where class_id=1 and student_id = 108084"): 
            print row
        
        print insert_record('2','108085',"i called the kid today, but did not pick up")   
        print insert_record('1','108084',"i called the kid today, but did not pick up")
        print insert_record('1','108084',"tried to call again")
        
        for row in cur.execute("SELECT * from RECORDS"): 
            print row
    """    
    