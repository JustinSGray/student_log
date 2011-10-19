#!/usr/bin/env python

from time import strptime,strftime
import re
import base64
import os

import sys, os
abspath = os.path.dirname(__file__)
if abspath: 
    sys.path.append(abspath)
    os.chdir(abspath)

import web
from web import form

web.config.debug = False

from roster_parser import parse_roster

from model import del_class, insert_class



db = web.database(dbn='sqlite', db='student_logs.db')

#need to make your own auth.txt file with username/passwords
allowed = [tuple(line.strip().split(",")) for line in open('auth.txt','rb')]

  

urls = ("/login","login",
       "/logout","logout",
       "/export","export_database",
       "/import","import_database",
       "/","classes",
       "/students", "students",
       "/students/(\d*)", "students",
       "/classes", "classes",
       "/classes/(\d*)"  , "classes",
       "/classes/(\d+)/multi-student-record", "multi_student_record",
       "/classes/(\d+)/students", "classes_students",
       "/classes/(\d+)/students/new", "new_classes_students",
       "/classes/(\d+)/students/(\d+)", "classes_students",
       "/classes/(\d+)/students/(\d+)/records","records",
       "/classes/(\d+)/students/(\d+)/proctor","proctor",
       "/classes/(\d+)/del","delete_classes",
       "/search","search")
       
app = web.application(urls, globals())
application = app.wsgifunc()

session = web.session.Session(app, web.session.DiskStore('sessions'), {'login': 0})


def time_fmt(timestr): 
    t = strptime(timestr,'%Y-%m-%d %H:%M:%S')
    if t.tm_hour < 12: 
        return strftime('%Y-%m-%d %I:%M:%S AM',t)
    else: 
        return strftime('%Y-%m-%d %I:%M:%S PM',t)
        
    
    
render = web.template.render('templates',globals={'zip': zip,'time_fmt':time_fmt})

def authenticate(): 
    if session.login==1: 
        return 
    raise web.seeother('/login')
    
    
        
		
class login(object): 
    def GET(self):  
        if session.login==1: 
           raise web.seeother("/")
           
        return render.login(render.header()) 
	
    def POST(self): 
        name, passwd = web.input().user, web.input().passwd
        if (name,passwd) in allowed:     
            session.login = 1
            raise web.seeother("/")
        else: 
            raise web.seeother("/login")    
class logout(object): 
    def GET(self): 
        session.kill()
        
        raise web.seeother("/login")            
                 
class export_database(object): 
    def GET(self): 
        authenticate()
        
        web.header('Content-Type','text/db')
        web.header('Content-disposition', 'attachment; filename=student_logs.db')
        
        return open('student_logs.db','rb')        

class import_database(object): 
    def GET(self): 
        return render.upload(render.header())
                
    def POST(self): 
        x = web.input(db_file={})  
        #x['db_file'].filename # This is the filename
        #x['db_file'].value # This is the file contents
        #x['db_file'].file.read() # Or use a file(-like) object
        fout = open('import_data.db','w') # creates the file where the uploaded file should be stored
        fout.write(x['db_file'].file.read()) # writes the uploaded file to the newly created file.
        fout.close() # closes the file, upload complete.
        
        t = db.transaction()
               
        q = "attach 'import_data.db' as import;"
        db.query(q)
        
        class_sync_map = {} #keyed by import key, value is new id
        
        #loop over all classes, check if any match and if not, insert
        q = "SELECT * from import.CLASSES"
        classes = db.query(q)
        
        for c in classes: 
            ret = db.select(tables="main.CLASSES",what="count(*) as total",where="name=$name and active=$active and date=$date",vars=c)
            if not ret[0].total:
                
                db.query("INSERT INTO CLASSES VALUES(Null,$name,$active,$date)",c)
                
                q = "SELECT last_insert_rowid()"
                new_id = db.query("SELECT last_insert_rowid() as id")[0]['id']
                
                class_sync_map[c.class_id] = new_id
            else: 
                class_sync_map[c.class_id] = c.class_id  
                    
        
        #loop over all students, check if any match and if not, insert
        q = "SELECT * from import.STUDENTS"
        students = db.query(q)
        
        for s in students: 
            ret = db.select(tables="main.STUDENTS",what="count(*) as total",
            where="student_id=$student_id",
            vars=s) 
            if not ret[0].total: 
                q = "INSERT INTO STUDENTS VALUES($student_id,$first_name,$last_name,$dec,"+\
                "$parent_name,$parent_email,$DOB,$grade,$phone_number,$r_score_in,$w_score_in,$r_score_out,$w_score_out,$notes)"
                db.query(q,vars=s)   
        
        #loop over all classes_students, check if any match and if not, insert
        
        q = "SELECT * from import.CLASSES_STUDENTS"
        classes_students = db.query(q)
        for cs in classes_students:   
            old_id = cs.class_id          
            cs.class_id = str(class_sync_map[int(cs.class_id)])
            cs.student_id = cs.student_id
            
            ret = db.select(tables="main.CLASSES_STUDENTS",what="count(*) as total",
            where="class_id=$class_id and student_id=$student_id",
            vars=cs)
            
            if not ret[0].total: 
                q = "INSERT INTO main.CLASSES_STUDENTS VALUES($class_id,$student_id,$status,$teach_assn)"
                db.query(q,vars=cs)
                
                
                q = "SELECT * from import.PROCTOR WHERE student_id=$student_id and class_id=$class_id"
                proctor = db.query(q,vars={'student_id':cs.student_id,'class_id':old_id})[0]
                proctor.class_id=cs.class_id
                
                q = "UPDATE main.PROCTOR SET q1=$q1,q1=$q2 WHERE student_id=$student_id and class_id=$class_id"
                db.query(q,vars=proctor)
                
            else:     
                #need to use logical or on q1/q2 from old and new dbs
                
                q = "UPDATE main.CLASSES_STUDENTS set status=$status, teach_assn=$teach_assn where student_id=$student_id and class_id=$class_id"
                db.query(q,vars=cs)
                
                
                q = "SELECT * from import.PROCTOR WHERE student_id=$student_id and class_id=$class_id"
                proctor_import = db.query(q,vars={'student_id':cs.student_id,'class_id':old_id})[0]
                
                q = "SELECT * from main.PROCTOR WHERE student_id=$student_id and class_id=$class_id"
                proctor_main = db.query(q,vars={'student_id':cs.student_id,'class_id':cs.class_id})[0]
                
                q = "UPDATE main.PROCTOR SET q1=$q1,q2=$q2 WHERE student_id=$student_id and class_id=$class_id"
                proctor_main.q1 = proctor_import.q1 or proctor_main.q1
                proctor_main.q2 = proctor_import.q2 or proctor_main.q2
                db.query(q,vars=proctor_main)
                
        #loop over all records, check if any match and if not, insert
        q = "SELECT * FROM import.RECORDS"
        records = db.query(q)
        
        for r in records: 
            r.class_id = class_sync_map[int(r.class_id)]
            
            ret = db.select(tables="main.RECORDS",what="count(*) as total",
            where="datetime=$datetime and class_id=$class_id and student_id=$student_id",
            vars=r)
            
            if not ret[0].total: 
                q = "INSERT INTO RECORDS values(Null,$datetime,$notes,$student_id,$class_id)"
                db.query(q,vars=r)
        
        t.commit()    
                
        q = "detach import;"
        db.query(q)
    
        os.remove('import_data.db')
        
  
        
        raise web.seeother("/")
        
 

class search(object): 
    def POST(self): 
        authenticate()
        search_term = web.input()['search_term']
        q = '''SELECT STUDENTS.student_id,first_name,last_name,phone_number,CLASSES.class_id FROM STUDENTS 
            LEFT JOIN RECORDS ON 
            STUDENTS.student_id = RECORDS.student_id
            LEFT JOIN CLASSES ON 
            RECORDS.class_id = CLASSES.class_id
            and CLASSES.active=1
            WHERE 
            STUDENTS.first_name LIKE $search_term
            OR 
            STUDENTS.last_name LIKE $search_term
            or 
            STUDENTS.phone_number LIKE $search_term
            or 
            STUDENTS.notes LIKE $search_term
            or 
            RECORDS.notes LIKE $search_term
            GROUP BY STUDENTS.student_id
            ORDER BY STUDENTS.last_name, STUDENTS.first_name, CLASSES.date
            '''
        students = db.query(q,vars={'search_term':"".join(["%",search_term,'%'])})

        return render.search(render.header(),search_term,students)

class students(object):
    #return a student object
    def GET(self,student_id=""):
        authenticate()
        #index 
        if not student_id: 
            students = db.query("SELECT * from STUDENTS")
            return render.students(render.header(),students)
            
        #get specific student
        else: 
            vars={'id':student_id}
            student = db.query("SELECT * from STUDENTS WHERE student_id=$id",vars=vars)[0]

            q = """SELECT * from CLASSES 
            JOIN CLASSES_STUDENTS ON 
                CLASSES.class_id=CLASSES_STUDENTS.class_id
            JOIN STUDENTS ON 
                CLASSES_STUDENTS.student_id=STUDENTS.student_id
            WHERE STUDENTS.student_id=$id    
            """
            
            classes =  db.query(q,vars=vars)

            return render.student(render.header(),student,classes)
        
    #update a student    
    def POST(self,student_id): 
        authenticate()
        params = web.input()
        params['student_id'] = student_id
        params['dec'] = 'dec' in params
        
        q=""
        if 'last_name' in params: 
            q = """UPDATE STUDENTS SET 
              last_name=$last_name,
              first_name=$first_name,
              dec=$dec,
              parent_name=$parent_name,
              grade=$grade,
              phone_number=$phone_number,
              r_score_in=$r_score_in,
              w_score_in=$w_score_in,
              r_score_out=$r_score_out,
              w_score_out=$w_score_out,
              notes=$notes
            WHERE student_id=$student_id
            """
        
        else:
            q = """UPDATE STUDENTS SET dec=$dec WHERE student_id=$student_id"""
  
        if q: 
          db.query(q,params)
        
        referer = web.ctx.env.get('HTTP_REFERER')
        if referer:
            raise web.seeother(referer)
            
        raise web.seeother('/student/%s'%student_id)

class delete_classes(object): 
    def GET(self,class_id=""): 
        authenticate()
                
        q = """DELETE FROM CLASSES WHERE class_id IN (%s)"""%class_id
        db.query(q)
        
        raise web.seeother("/")
                    
class classes(object):
    def GET(self,class_id=""):
        authenticate()
        if not class_id: 
            active_classes = db.query("""SELECT * FROM CLASSES
            WHERE active=1 ORDER BY date DESC""")
            
            other_classes = db.query("""SELECT * FROM CLASSES 
            WHERE active=0 ORDER BY date DESC""")
            
            return render.classes(render.header(),active_classes,other_classes)
  
        else: #get specific class
            vars={'id':class_id}
            class_ =  db.query("SELECT * FROM CLASSES WHERE class_id=$id",
                             vars=vars)[0]
            
            q = """SELECT * from CLASSES 
            JOIN CLASSES_STUDENTS ON 
                CLASSES.class_id=CLASSES_STUDENTS.class_id
            JOIN STUDENTS ON 
                CLASSES_STUDENTS.student_id=STUDENTS.student_id
            JOIN PROCTOR ON 
                PROCTOR.class_id=CLASSES.class_id AND 
                PROCTOR.student_id=STUDENTS.student_id
            WHERE CLASSES.class_id=$id AND CLASSES_STUDENTS.status="ENR"
            ORDER BY STUDENTS.last_name,STUDENTS.first_name
            """
                
            enr_students =  db.query(q,vars=vars)
            
            
            q = """SELECT * from CLASSES 
            JOIN CLASSES_STUDENTS ON 
                CLASSES.class_id=CLASSES_STUDENTS.class_id
            JOIN STUDENTS ON 
                CLASSES_STUDENTS.student_id=STUDENTS.student_id
            JOIN PROCTOR ON 
                PROCTOR.class_id=CLASSES.class_id AND 
                PROCTOR.student_id=STUDENTS.student_id
            WHERE CLASSES.class_id=$id AND CLASSES_STUDENTS.status="WD "
            ORDER BY STUDENTS.last_name,STUDENTS.first_name
            """
            wdr_students =  db.query(q,vars=vars)
            
            q = """SELECT * from CLASSES 
            JOIN CLASSES_STUDENTS ON 
                CLASSES.class_id=CLASSES_STUDENTS.class_id
            JOIN STUDENTS ON 
                CLASSES_STUDENTS.student_id=STUDENTS.student_id
            JOIN PROCTOR ON 
                PROCTOR.class_id=CLASSES.class_id AND 
                PROCTOR.student_id=STUDENTS.student_id
            WHERE CLASSES.class_id=$id AND CLASSES_STUDENTS.status="ADM"
            ORDER BY STUDENTS.last_name,STUDENTS.first_name
            """
            adm_students =  db.query(q,vars=vars)
            
            error = web.input().get('error')
            
            return render.class_(render.header(),class_,
            enr_students,wdr_students,adm_students,error) 
            
    def POST(self,class_id=""): 
        authenticate()
        if class_id: 
            vars = {'active':'active' in web.input(),'class_id':class_id}
            
            db.query('UPDATE CLASSES SET active=$active WHERE class_id=$class_id',
                     vars)
                     
            raise web.seeother('/classes')
        else: 
            params = web.input()
            vars = {'active':True,'name':params['name']} 
            
            db.query("INSERT INTO CLASSES VALUES(Null,$name,$active,date('now'))",vars)
            
            raise web.seeother('/classes')
    
    
multi_student_record_form = form.Form(
    form.Textarea('notes'),
    form.Textarea('ids'),        
    )
            
new_record = form.Form(
    form.Textarea('notes',
                  rows="4",cols="80",
                  description=""),
    form.Button('Save')
    )    
    
new_proctor = form.Form(
    form.Checkbox('q1',description="First Quarter"),
    form.Checkbox('q2',description="Second Quarter"),
    #form.Button('Save')
    )      
    
checked_map = {True:'checked',False:''}  
class new_classes_students(object): 
    def GET(self,class_id): 
    	authenticate()
        vars={'id':class_id}
        class_ =  db.query("SELECT * FROM CLASSES WHERE class_id=$id",
                           vars=vars)[0]
        new_proc = new_proctor()
        return render.new_class_student(render.header(),class_,new_proc)
    
    def POST(self,class_id):
        authenticate()
        params = web.input()
        params['parent_email'] = ""
        q = """SELECT * FROM STUDENTS 
        LEFT JOIN CLASSES_STUDENTS ON 
            STUDENTS.student_id=CLASSES_STUDENTS.student_id
        LEFT JOIN CLASSES ON
            CLASSES_STUDENTS.class_id=$class_id
        WHERE STUDENTS.student_id=$student_id
        """
        params['class_id'] = class_id
        params['dec'] = 'dec' in params
        ret = db.query(q,params)
        
        add_to_class = """INSERT INTO CLASSES_STUDENTS 
        VALUES($class_id,$student_id,$status,$teach_assn)
        """ 

        new_student = """INSERT INTO STUDENTS VALUES($student_id,
                     $first_name,
                     $last_name,
                     $dec,
                     $parent_name,
                     $parent_email,
                     Null,
                     $grade,
                     $phone_number,
                     $r_score_in,
                     $w_score_in,
                     $r_score_out,
                     $r_score_out,$notes)"""
        
        for student_class in ret: #then there is already a student
            if student_class.class_id==class_id:
                raise web.seeother('/classes/%s/students/%s'%(class_id,params['student_id']))
            else: 
                db.query(add_to_class,params)
                raise web.seeother('/classes/%s/students/%s'%(class_id,params['student_id']))
            break
        else: #create the student  
            db.query(new_student,params)
            db.query(add_to_class,params)
        
        raise web.seeother("/classes/%s/students/%s"%(class_id,params['student_id']))         
class classes_students(object): 
    def GET(self,class_id,student_id): 
        authenticate()
        vars={'class_id':class_id,'student_id':student_id}

        q = """SELECT * from CLASSES 
        JOIN CLASSES_STUDENTS ON 
            CLASSES.class_id=CLASSES_STUDENTS.class_id
        JOIN STUDENTS ON 
            CLASSES_STUDENTS.student_id=STUDENTS.student_id
        JOIN PROCTOR ON 
            PROCTOR.class_id=CLASSES.class_id AND
            PROCTOR.student_id=STUDENTS.student_id
        WHERE CLASSES.class_id=$class_id AND STUDENTS.student_id=$student_id
        """
        
        class_student = db.query(q,vars=vars)[0]        
        q = """SELECT * FROM RECORDS
        JOIN CLASSES ON RECORDS.class_id=CLASSES.class_id
        WHERE RECORDS.student_id=$student_id
        ORDER BY RECORDS.datetime DESC
            """
        records = db.query(q,vars)
        
        new_rec = new_record()
        
        #dirty hack to get the forms working for filling check boxes
        new_proctor = form.Form(
            form.Checkbox('q1',description="First Quarter",value="1",
                          checked=class_student.q1),
            form.Checkbox('q2',description="Second Quarter",value="1",
                          checked=class_student.q2),
            #form.Button('Save')
        )   
        
        
        new_proc = new_proctor()
        
        return render.class_student(render.header(),class_student,new_proc,records,new_rec)
        
    def POST(self,class_id,student_id=""):
        authenticate()
        if student_id: #edit one student
            params = web.input()
            status = params.get('status')
            teach_assn = params.get('teach_assn')
            
            if status and teach_assn: 
                q = """UPDATE CLASSES_STUDENTS SET status=$status,teach_assn=$teach_assn WHERE
                class_id=$class_id AND student_id=$student_id"""
            elif teach_assn:  
                q = """UPDATE CLASSES_STUDENTS SET teach_assn=$teach_assn WHERE
                class_id=$class_id AND student_id=$student_id"""
            else: 
                q = """UPDATE CLASSES_STUDENTS SET status=$status WHERE
                class_id=$class_id AND student_id=$student_id"""
                
            vars = {'class_id':class_id,'student_id':student_id,
                    'status':status,'teach_assn':teach_assn}
            db.query(q,vars)
            
                
            referer = web.ctx.env.get('HTTP_REFERER')
            if referer:
                raise web.seeother(referer)
        
            raise web.seeother('/classes/%s/students/%s'%(class_id,student_id))
        
        else: #upload roster 
            params = web.input(roster={})
            file = params['roster']
            
            try: 
                data = parse_roster(file.file)
                
            except KeyError,err: 
                error = "there was a problem parsing the given csv file. The column, '%s' was not present"%str(err)
                
                raise web.seeother('/classes/%s?error=%s'%(class_id,error))
       
            q0="""SELECT student_id FROM STUDENTS WHERE student_id=$student_id"""
            
        
            q1="""INSERT INTO STUDENTS VALUES($student_id,
                     $first_name,
                     $last_name,
                     $dec,
                     $parent_name,
                     Null, 
                     Null,
                     $grade,
                     $phone_number,
                     $r_score_in,
                     $w_score_in,
                     Null,Null,Null)"""
                 #WHERE NOT EXISTS (SELECT * FROM STUDENTS WHERE student_id=$student_id)"""
            
            q2="""SELECT * FROM CLASSES_STUDENTS WHERE 
                  class_id=$class_id AND student_id=$student_id"""
            
            q3="""INSERT INTO CLASSES_STUDENTS VALUES($class_id,$student_id,
            $status,"GenEd")"""    
             
            for row in data:
                 row['class_id'] = class_id 
                  
                 check = db.query(q0,row)
                 if not check: db.query(q1,row)
                  
                 check = db.query(q2,row)
                 if not check :db.query(q3,row)
             
            referer = web.ctx.env.get('HTTP_REFERER')
            if referer:
                raise web.seeother(referer)
                
            raise web.seeother('/classes/%s'%class_id)
                    
        
class records(object): 
    def POST(self,class_id,student_id,record_id=""): 
        ''' create a new record'''
        authenticate()
 
        vars={'class_id':class_id,'student_id':student_id,
                'notes':web.input().notes,'record_id':record_id}
        if record_id: 
            q="""UPDATE RECORDS SET notes=$notes
                 WHERE record_id=$record_id"""
        else: 
            q="""INSERT INTO RECORDS (class_id,student_id,notes,datetime) 
                 VALUES($class_id,$student_id,$notes,datetime('now','localtime'))"""
            
        db.query(q,vars)
            
        raise web.seeother('/classes/%s/students/%s'%(class_id,student_id))
 

class multi_student_record(object): 
    def POST(self,class_id,record_id=""): 
    	authenticate()
        form = multi_student_record_form()
        form.validates()
        ids = form['ids']
        notes = form['notes'].value
        ids = ids.value.split(",")
        
        for student_id in ids: 
            vars={'class_id':class_id,'student_id':student_id,
                'notes':notes,'record_id':record_id}
            if record_id: 
                q="""UPDATE RECORDS SET notes=$notes
                     WHERE record_id=$record_id"""
            else: 
                q="""INSERT INTO RECORDS (class_id,student_id,notes,datetime) 
                     VALUES($class_id,$student_id,$notes,datetime('now','localtime'))"""
            
       	    db.query(q,vars) 
            
        
        
class proctor(object): 
    def POST(self,class_id,student_id): 
        '''update the proctor of a student in a particular class'''
        authenticate()
        form = new_proctor()
        form.validates()
        q1 = 'q1' in web.input()
        q2 = 'q2' in web.input()
        
        
        vars={'class_id':class_id,'student_id':student_id,
              'q1':q1,'q2':q2}
              
        q="""UPDATE PROCTOR SET q1=$q1, q2=$q2 
        WHERE class_id=$class_id and student_id=$student_id"""
        
        db.query(q,vars)
        
        referer = web.ctx.env.get('HTTP_REFERER')
        if referer:
            raise web.seeother(referer)
        
        raise web.seeother('/classes/%s/students/%s'%(class_id,student_id))
  
    
if __name__ == "__main__":
    #from multiprocessing import Process
    #Process(target=launch_browser).start()
    app.run()
    