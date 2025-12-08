# Dev-or-Die-Team-Ai-Essence
This repository contains all files related to our Dev-or-Die project.
PS:4 Intelligent Document Console
1.We have created an AI powered document processing system that allows user to manage , view and delete their documents and other functionalities.
  Implemented Features are:
  > Semantic search across all uploaded documents using chunk level embeddings
  > OCR for images
  > Auto Summarising and categorising
  > Text extraction
  > View or delete previous files 
2.Tech stack :
  > Html and CSS for Frontend
  > Flask used for Backend
  > MySQL(XAMPP server) for database management , storing uploaded files
  > Google-Generative Ai(Gemini)'s API for AI tasks
  > SentenceTransformer for embeddings
  > pdf2image and poppler to convert pdf into image 
3.API documentation:
  >POST (/upload) renders process.html
  >POST (/search) renders search_result.html
  >GET (/files) renders files.html
  >GET (/view/<int:File_id>) renders process.html
  >GET (/delete/<int:File_id>) renders /files
4.About TEAM:
  >Backend developer : Suraj Kumar Patel(Leader)
  >Frontend developers : Shravan jaiswal(Html) , Mayank Jain(CSS)
  >Database handling : Shreyansh Maurya 
5.Installation And Setup Instructions
  >Install Python packages
    >pip install -r requirements.txt
  >create virtualenv
    >python -m venv venv
    >.\venv\Scripts\activate
  >Set up MySQL
    >Open phpMyAdmin (via XAMPP)
    >create database named file_db
    >select file_db and go to import
    >download and choose file from repository named file_db.sql
    >click import
  >Set your Gemini Api key
    >write your gemini api key in line 16
    >you can generate free key at https://aistudio.google.com/app/apikey
  >Install and add Poppler to path 
  >Install pdf2image using 'pip install google-generativeai pdf2image pillow'
  >Run the file app.py in your python virtualenv
6.Future Improvements:
  >Masking and demasking
  >User authentication system
  >Multi-document combined summary
7.AI/ML integration:
  >gemini-2.5-flash for summarising and catgorising
  >SentenceTransformer(all-MiniLM-l6-v2) for embeddings
  >pdf2image for converting pdf into images  
