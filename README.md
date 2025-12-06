# Dev-or-Die-Team-Ai-Essence
This repository contains all files related to our Dev-or-Die project.
1.We have created an AI powered document processing system that allows user to:
  >upload pdfs
  >extract text from pdfs
  >automatically generate summary and category
  >generate sentence level embeddings
  >store all results in MySQL database
  >perform sementic search across all uploaded files
  >view and delete previously uploaded files
  It uses Groq Llama-3.1-8B-instant for Ai powered tasks and SentenceTransformer(all-MiniLM-L2-v2) for embeddings
2.Installation And Setup Instructions
  >Install Python packages
    >pip install -r requirements.txt
  >create virtualenv
    >python -m venv venv
    >.\venv\Scripts\activate
  >Set up MySQL
    >Open phpMyAdmin (via XAMPP)
    >create database named file_db
    >select file_db and go to import
    >choose file from repository named file_db.sql
    >click import
  >Set your Groq Api key
    >write your groq api key in line 16
    >you can generate free key at  https://console.groq.com/keys
  >Run the file app.py in your python virtualenv
