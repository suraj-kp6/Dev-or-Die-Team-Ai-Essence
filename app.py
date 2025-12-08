from flask import Flask , render_template,request,redirect,url_for
from flask_mysqldb import MySQL,MySQLdb 
import google.generativeai as genai
from pdf2image import convert_from_path as convert
from sentence_transformers import SentenceTransformer
import json
import numpy

app = Flask(__name__)

app.secret_key="suraj"
app.config["MYSQL_HOST"] = 'localhost'
app.config["MYSQL_USER"] = 'root'
app.config["MYSQL_DB"] = 'file_db'
db = MySQL(app)
genai.configure(api_key="AIzaSyAOGBWVs2WlMdnfobywTOLjI8cfadKAzTA")
model = genai.GenerativeModel("gemini-2.5-flash")
emb = SentenceTransformer("all-MiniLM-l6-v2")

def pdf_to_image(path):
    pages = convert(path,dpi=200)
    return pages
def text_from_image(img):
    response = model.generate_content(["Extract all readable text from this image accurately:",img])
    return response.text.strip()
def ocr(path):
    images = pdf_to_image(path)
    text =""
    for i,img in enumerate(images):
        print("Processing page{i+1}...")
        page_text = text_from_image(img)
        text += page_text +"\n\n"
    return text
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
        if name.lower().endswith(".pdf"):
           text = ocr("uploaded.pdf")  
        else:
           text = file.read().decode("utf-8")
        #summarising
        summary = model.generate_content("Please summarise the document text provided and give the summary in points").text
        #categorising
        category = model.generate_content("Read the document and classify it into one category fro, the following : [Research document, story, intelligence report, mission briefing ],  If it does not fit to any category then give it your own category but return category only nothing else\n\n{text}").text.strip()
        #embeddings for semantic search
        emb_vector = emb.encode(text).tolist()
        global emb_json
        emb_json = json.dumps(emb_vector)
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
