from flask import Flask , render_template,request,redirect,url_for
from flask_mysqldb import MySQL,MySQLdb  # type: ignore
from PyPDF2 import PdfReader
from groq import Groq
from sentence_transformers import SentenceTransformer
import json
import numpy

app = Flask(__name__)

app.secret_key="suraj"
app.config["MYSQL_HOST"] = 'localhost'
app.config["MYSQL_USER"] = 'root'
app.config["MYSQL_DB"] = 'file_db'
db = MySQL(app)
groq_client = Groq(api_key="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")
emb = SentenceTransformer("all-MiniLM-L6-v2")

def chunk_text(text, max_length=500):
    sentences = text.split(". ")
    chunks = []
    chunk = ""
    for s in sentences:
        if len(chunk) + len(s) < max_length:
            chunk += s + ". "
        else:
            chunks.append(chunk.strip())
            chunk = s + ". "
    if chunk:
        chunks.append(chunk.strip())
    return chunks

@app.route("/")
def home():
    return render_template('input.html')
@app.route("/upload",methods=["POST","GET"])
def upload():
    if request.method == "POST":
     global file,name,text,summary,category
     file = request.files['file']
     name = file.filename
     if name!="":
        file.save("uploaded.pdf")
        reader = PdfReader("uploaded.pdf") 
        text = ""
        for page in reader.pages:
            ext = page.extract_text()
            if ext:
                text += ext + "\n"
        #summarising
        response = groq_client.chat.completions.create(model="llama-3.1-8b-instant",messages=[{"role":"system","content":"Summarize this"},{"role":"user","content":text}])
        summary=response.choices[0].message.content.strip()
        #categorising
        category_response = groq_client.chat.completions.create(model="llama-3.1-8b-instant",
        messages=[{"role": "system", "content": "Read the document and classify it into ONE category from the following: mission briefing, enemy report, megazord maintenance, research document, intelligence note, strategy plan. Return only the category name."},{"role": "user", "content": text}])
        category = category_response.choices[0].message.content.strip()
        #embeddings for semantic search
        
        embedding_vector = emb.encode(text).tolist()
        global emb_json
        emb_json = json.dumps(embedding_vector)
        #storing in database
        cur = db.connection.cursor()
        query = "Insert into uploaded_files(Filename,File,Filetext,Summary,Category,Embeddings) values(%s,%s,%s,%s,%s,%s)"
        cur.execute(query,(name,file,text,summary,category,emb_json))
        db.connection.commit()
        SRno = cur.lastrowid
        chunks = chunk_text(text)
        for ch in chunks:
            ch_vec = emb.encode(ch).tolist()
            ch_vectors_json = json.dumps(ch_vec)
            cur.execute("INSERT INTO file_chunks (SRno, chunk_text, chunk_emb) VALUES (%s, %s, %s)",(SRno, ch, ch_vectors_json))
            db.connection.commit()
        cur.close
        return render_template("process.html",filename=name,text=text,summary=summary,category=category)
     else:
        return redirect("/upload")
    else:
        return render_template("process.html",filename=name,text=text,summary=summary,category=category)
@app.route("/search",methods=["POST","GET"])
def search():
    if request.method=="POST":
     search_query=request.form["query"]
     query_vec= emb.encode(search_query)
     cur = db.connection.cursor()
     cur.execute("SELECT uploaded_files.Filename, file_chunks.chunk_text, file_chunks.chunk_emb FROM file_chunks JOIN uploaded_files ON uploaded_files.SRno = file_chunks.SRno")
     rows = cur.fetchall()
     cur.close()
     results = []
     for filename, ch_text, emb_json in rows:
            doc_vec = numpy.array(json.loads(emb_json))
            score = float(numpy.dot(query_vec, doc_vec) /
                          (numpy.linalg.norm(query_vec) * numpy.linalg.norm(doc_vec)))
            results.append({"filename": filename,"chunk": ch_text,"score": score})
     results = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
     return render_template("search_result.html", results=results)
    else:
        return render_template("process.html")
@app.route("/files")
def database():
    cur = db.connection.cursor()
    cur.execute("Select SRno , Filename From uploaded_files")
    rows = cur.fetchall()
    cur.close()
    files=[]
    for i,row in enumerate(rows,start =1):
        srno,filename =row
        files.append({"Serial_Number":i,"File_id":srno,"Name":filename})
    return render_template("files.html",files=files) 
@app.route("/view/<int:File_id>")        
def viewfile(File_id):
    cur=db.connection.cursor()
    cur.execute("Select Filename,Filetext,Summary,Category From uploaded_files where SRno = %s",(File_id,))
    row =cur.fetchone()
    cur.close()
    if row:
        name,text,summary,category = row
        return render_template("process.html",filename=name,text=text,summary=summary,category=category)
    else:
        return "404 Error !!\nFILE NOT FOUND"
@app.route("/delete/<int:File_id>")
def deletefile(File_id):
    cur = db.connection.cursor()
    cur.execute("Delete from file_chunks where SRno =%s",(File_id,))
    cur.execute("Delete from uploaded_files where SRno =%s",(File_id,))
    db.connection.commit()
    cur.close()
    return redirect(url_for("database"))
app.run(debug = True)