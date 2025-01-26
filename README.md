# Rust RAG

A simple Retrieval-Augmented Generation (RAG) system that uses [Rust crate documentation]((https://docs.rs)) to answer questions.

## Features

- Download crate docs

## To-Dos

- **Download Crates**
  - [x] Implement the logic to download Rust crate documentation.
  - [ ] Implement the logic to parse the downloaded documentation.
- **Chunking Strategy**
  - [ ] Fixed-Size Chunking (with Token Count)  
        Divide the text into chunks that have a maximum number of tokens, with an optional overlap.
  - [ ] Sentence-Based Chunking  
        Split the text into chunks at sentence boundaries.
  - [ ] Paragraph-Based Chunking  
        Split the text at paragraph breaks.
  - [ ] Recursive Chunking  
        Break down the text recursively based on different criteria. For example, it can be broken by paragraphs, then sentences, and then by tokens if needed.
  - [ ] Context-Aware Chunking  
        Split text based on semantic meaning, such as identifying headings, subheadings, or topic shifts.
- **Storing Embeddings**
  - [ ] Implement indexing of embeddings into a vector database.
  - [ ] Implement retrieval of relevant chunks from the vector database based on queries.
  - [ ] Index the embeddings, with a reference to the original text.
- **RAG Pipeline:**
  - [ ] Query Processing  
        Embed the user's query using the same embedding model used for the documentation.
  - [ ] Retrieval  
        Query the vector database to find the most similar document chunks to the query.
  - [ ] Generation  
        Feed the retrieved context into a language model to generate the answer.
- **LLM integration:**
  - [ ] Select a LLM provider
  - [ ] Implement the logic to interface with the chosen LLM.
- **Documentation:**
  - [ ] Add documentation to the code.
  - [ ] Update the README with detailed instructions.
