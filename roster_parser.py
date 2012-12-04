from csv import DictReader


student_row_keys = [
        ('student_id','SEPID'),
        ('last_name','Last Name'),
        ('first_name','First Name'),
        ('dec','DEC'),
        ('parent_name','Parent/Legal Guardian'),
        ('parent_email','ECOT Parent/Legal Guardian Email'),
        ('grade', 'Gr'),
        ('phone_number',('Home','Parent Cell','Student Cell')),
        ('status','Stat'),
        ('enr_date','Enr'),
        ('r_score_in','OGT Rdg'),
        ('w_score_in','OGT Wri')]

def parse_roster(file): 
    #skip initial lines
    file.readline()  
    file.readline()
    file.readline()
    file.readline()
    
    reader = DictReader(file)
    data = []
    for line in reader: 
        row = {}
        #print "test: ",line
        for my_key,their_key in student_row_keys: 
            if my_key == "phone_number": 
                home = line[their_key[0]]
                p_cell = line[their_key[1]]
                s_cell = line[their_key[2]]
                
                if home: row[my_key] = home
                elif p_cell: row[my_key] = p_cell
                elif s_cell: row[my_key] = s_cell
            elif my_key == "dec": 
               row[my_key] = bool(line[their_key])    
            else:     
                row[my_key] = line[their_key]
        data.append(row)   
    return data
    
    
    
if __name__=="__main__":
    roster = open('K12_CourseRosterOGT.csv','rU')

    print parse_roster(roster)
    
    