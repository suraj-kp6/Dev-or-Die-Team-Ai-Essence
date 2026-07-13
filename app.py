from flask import Flask , render_template,request,redirect,url_for
from flask_mysqldb import MySQL
from sentence_transformers import SentenceTransformer
import easyocr
from pdf2image import convert_from_path as convert
import os
import json
import numpy
from dotenv import load_dotenv
import requests
app = Flask(__name__)
load_dotenv()

app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER", "root")
app.config["MYSQL_DB"] = os.getenv("MYSQL_DB", "file_db")

db = MySQL(app)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

OLLAMA_URL = os.getenv("OLLAMA_URL","http://localhost:11434/api/generate")

reader = easyocr.Reader(['en'])

poppler_path = os.getenv("POPPLER_PATH")

def ask_ollama(prompt):
        try:
            response = requests.post(OLLAMA_URL,json={"model": "gemma3:4b","prompt": prompt,"stream": False},
                                timeout=120)
            response.raise_for_status()
            return response.json()["response"]
        except requests.exceptions.RequestException:
            return "Error: Unable to connect to Olllama. Please make sure Ollama is running."

def pdf_to_image(path):
    pages = convert(path,dpi=200,poppler_path=poppler_path)
    return pages

def text_from_image(image_path):
    result = reader.readtext(image_path, detail=0)
    return "\n".join(result)

def ocr(path):
    images = pdf_to_image(path)
    text = ""
    for i, img in enumerate(images):
        temp = f"page_{i}.png"
        img.save(temp)
        print(f"Processing page {i+1}...")
        page_text = text_from_image(temp)
        text += page_text + "\n\n"
        os.remove(temp)
    return text

def chunk_text(text, max_chars):
    paragraphs = text.split("\n")
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += para + "\n"
        else :
            if len(current)!=0:
                chunks.append(current)
            current = para + "\n"
    if(current):
        chunks.append(current)
    return chunks

def summarise(chunks):
    partial_summaries = []
    for i, ch in enumerate(chunks):
        print(f"Summarizing chunk {i+1}/{len(chunks)}")
        summary = ask_ollama(f""" You are an AI document analysis assistant. Summarize the following section of a document.
                             Instructions:
                             - Use concise bullet points.
                             - Preserve important facts, names, numbers, dates and technical terms.
                             - Do NOT repeat information.
                             - Limit the summary to 6-10 bullet points.
                             Document Section: {ch}""")
        partial_summaries.append(summary)
    combined = "\n".join(partial_summaries)
    final_summary = ask_ollama(f"""You are an AI document analysis assistant. The following are summaries of different sections of the SAME document. Create one final document summary.
                               Requirements:
                               - Merge overlapping points.
                               - Remove duplicate information.
                               - Keep the summary well organized.
                               - Use bullet points.
                               - Mention important people, organizations, dates and conclusions.
                               - If the document contains recommendations or decisions, include them.
                               - Keep the final summary under 20 bullet points.
                               Section Summaries: {combined}""")
    return final_summary

def categorise(text):
    return  ask_ollama(f"""You are an intelligent document classifier. Classify the following document into ONE category only.
                       Possible categories:
                       - Research Paper
                       - Intelligence Report
                       - Mission Briefing
                       - Technical Documentation
                       - Business Report
                       - Legal Document
                       - Financial Report
                       - Medical Document
                       - Educational Material
                       - News Article
                       - Resume/CV
                       - Story/Fiction
                       - Government Document
                       - Manual/Guide
                       - Other
                       Rules:
                       - Return ONLY the category name on first line.
                       - move on to the next line
                       - Explain your answer briefly in 1-2 lines from the second line.

                       Document: {text[:5000]}""") 

def find_best_chunk(file_id, query):
    query_vec = numpy.array(embedding_model.encode(query))

    cur = db.connection.cursor()
        
    cur.execute("""SELECT chunk_text, chunk_emb FROM file_chunks WHERE SRno=%s""",(file_id,))

    chunks = cur.fetchall()
    cur.close()

    best_chunk = ""
    best_score = -1

    for ch_text, emb_json in chunks:
        chunk_vec = numpy.array(json.loads(emb_json))
        score = float( 
            numpy.dot(query_vec, chunk_vec) /
            (numpy.linalg.norm(query_vec) * numpy.linalg.norm(chunk_vec))
            )
        if score > best_score:
            best_score = score
            best_chunk = ch_text

    best_score = round(best_score * 100, 2)
    return best_chunk , best_score

@app.route("/")
def home():
    return render_template('input.html')

@app.route("/upload",methods=["POST","GET"])
def upload():
    if request.method == "POST":
        file = request.files['file']
        name = file.filename
        
        ext = os.path.splitext(name)[1].lower()
        filename = "uploaded" + ext
        file.save(filename)
        try:
            if ext == ".pdf":
                text = ocr(filename)
            elif ext in [".png", ".jpg", ".jpeg"]:
                text = text_from_image(filename)
            elif ext == ".txt":
                file.seek(0)
                text = file.read().decode("utf-8")
            else:
                return "Unsupported file format"
        
            if not text.strip():
                return "No readable text found."
        
            #summarising
            summary = summarise(chunk_text(text,6000));
            #categorising
            category = categorise(text)       
            #embeddings for semantic search
            emb_vector = embedding_model.encode(text).tolist()
            emb_json = json.dumps(emb_vector)

            #storing in database
            cur = db.connection.cursor()
            query = "Insert into uploaded_files(Filename,Filetext,Summary,Category,Embeddings) values(%s,%s,%s,%s,%s)"
            file.seek(0)
            cur.execute(query,(name, text, summary, category, emb_json))
            db.connection.commit()
            SRno = cur.lastrowid
            chunks = chunk_text(text,600)
            for ch in chunks:
                ch_vec = embedding_model.encode(ch).tolist()
                ch_vectors_json = json.dumps(ch_vec)
                cur.execute("INSERT INTO file_chunks (SRno, chunk_text, chunk_emb) VALUES (%s, %s, %s)",(SRno, ch, ch_vectors_json))
            db.connection.commit()
            cur.close()
        finally:
            if os.path.exists(filename):
                os.remove(filename) 
        return render_template("process.html",file_id=SRno,filename=name,text=text,summary=summary,category=category)
    return redirect("/")

@app.route("/search",methods=["POST","GET"])
def search():
    if request.method=="POST":
        search_query=request.form["query"]
        query_vec = numpy.array(embedding_model.encode(search_query))

        cur = db.connection.cursor()
        cur.execute("SELECT  uploaded_files.SRno ,uploaded_files.Filename, file_chunks.chunk_text, file_chunks.chunk_emb FROM file_chunks JOIN uploaded_files ON uploaded_files.SRno = file_chunks.SRno")
        rows = cur.fetchall()
        cur.close()

        best_results = {}
        for file_id, filename, ch_text, emb_json in rows:
            doc_vec = numpy.array(json.loads(emb_json))
            score = float(
                numpy.dot(query_vec, doc_vec) / (numpy.linalg.norm(query_vec) * numpy.linalg.norm(doc_vec))
            )
            score = round(score * 100, 2)

            if file_id not in best_results or score > best_results[file_id]["score"]:
                best_results[file_id] = {
                "file_id": file_id,
                "filename": filename,
                "chunk": ch_text[:350] + "..." if len(ch_text) > 350 else ch_text,
                "score": score
                }  
        results = sorted( best_results.values(), key=lambda x: x["score"],reverse=True )[:5]
    
        return render_template("search.html", results=results)
    else:
        return render_template("search.html",results=None)

@app.route("/files")
def database():
    cur = db.connection.cursor()
    cur.execute("Select SRno , Filename From uploaded_files")
    rows = cur.fetchall()
    cur.close()
    files=[]
    for i,row in enumerate(rows,start =1):
        srno,filename =row
        files.append({"Serial_Number":i,"file_id":srno,"Name":filename})
    return render_template("files.html",files=files) 

@app.route("/view/<int:file_id>")        
def viewfile(file_id):
    cur=db.connection.cursor()
    cur.execute("""SELECT Filename , Filetext, Summary, Category FROM uploaded_files WHERE SRno=%s""", (file_id,) )
    row =cur.fetchone()
    cur.close()
    if row:
        name,text,summary,category = row
        return render_template("process.html",file_id=file_id,filename=name,text=text,summary=summary,category=category)
    else:
        return "404 Error !!\nFILE NOT FOUND"
    
@app.route("/delete/<int:file_id>")
def deletefile(file_id):
    cur = db.connection.cursor()
    cur.execute("Delete from file_chunks where SRno =%s",(file_id,))
    cur.execute("Delete from uploaded_files where SRno =%s",(file_id,))
    db.connection.commit()
    cur.close()
    return redirect(url_for("database"))

@app.route("/ask/<int:file_id>")
def ask_page(file_id):
    source = request.args.get("from", "process")
    cur = db.connection.cursor()

    cur.execute(
        "SELECT Filename FROM uploaded_files WHERE SRno=%s",
        (file_id,)
    )

    row = cur.fetchone()

    cur.close()

    if row is None:
        return "404 File Not Found"

    filename = row[0]

    return render_template(
        "askLLM.html",
        file_id=file_id,
        filename=filename,
        answer=None,
        source = source
    )

@app.route("/ask", methods=["POST"])
def askLLM():
    source = request.form["source"]
    

    file_id = request.form["file_id"]
    question = request.form["question"]

    best_chunk,_ = find_best_chunk(file_id, question)

    cur = db.connection.cursor()
    cur.execute("SELECT Filename FROM uploaded_files WHERE SRno = %s",(file_id,))
    row = cur.fetchone()
    cur.close()

    if row is None :
        return "404 FIle not found"
    
    filename = row[0]

    prompt = f"""
    You are an AI assistant that answers questions using only the provided document section.
    
    Rules: 
    - Answer only from the document section below.
    - If the answer is not contained in the section, say:
    "I couldn't find that information in the provided document."
    - Keep your answer concise and accurate.
    
    Document Section:
    {best_chunk}
    
    Question:
    {question}"""

    answer = ask_ollama(prompt)

    return render_template(
    "askLLM.html",
    file_id=file_id,
    filename=filename,
    answer=answer,
    source = source
)

@app.route("/search/view",methods=["POST"])
def view_search():

    file_id = request.form["file_id"]
    search_query = request.form["query"]

    best_chunk , best_score = find_best_chunk(file_id,search_query)
    cur = db.connection.cursor()
    cur.execute("""SELECT Filename , Summary, Category FROM uploaded_files WHERE SRno=%s""", (file_id,) )

    row =cur.fetchone()
    cur.close()

    if row is None:
        return "404 File Not Found"

    filename , summary , category = row

    return render_template( "view_search.html",
    file_id=file_id,
    filename=filename,
    summary=summary,
    category=category,
    matched_chunk=best_chunk,
    score=best_score )
    
if __name__ == "__main__":
    app.run(debug = True)