import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_spitter import RecursiveCharacterTextSplitter
from langchain_core.document import Document
from langchain_chroma import Chroma
import pdfplumber
load_dotenv()


class Application:
    def __init__(self, chunksize: int = 500, chunk_overlap: int = 100):
        self.chunksize = chunksize
        self.chunk_overlap = chunk_overlap
        self.model = ChatGoogleGenerativeAI(model="gpt-4o", api_key=os.getenv("api_key"), temperature=0)
        self.embeddings = GoogleGenerativeAIEmbeddings(model = "text-embedding-3-small", api_key=os.getenv("api_key"))
        self.vector_store = Chroma(collection_name="agentic_rag_docs",
                       embedding_function=self.embeddings,
                       persist_directory = "history"
                       )
    
    

    def get_data(self):
        doc_list = []
        doc_names = []
        wd = os.getcwd()
        target_dir = os.path.join(wd, "data")
        #Collect data
        for file in os.listdir(target_dir):
            if file.endswith(".txt"):
                with open(os.path.join(target_dir, file), "r", encoding="utf-8") as f:
                    doc_list.append(f.read())
                    doc_names.append(file)
            elif file.endswith(".pdf"):
                with pdfplumber.open(os.path.join(target_dir, file)) as pdf:
                    content = ""
                    for page in pdf.pages:
                        content += page.extract_text()
                    doc_list.append(content)
                    doc_names.append(file)

        documents = []
        for i, doc in enumerate(doc_list):
            documents.append(Document(page_content=doc, metadata={"filename": doc_names[i], "doc_count": len(doc)}))
        text_splitter = RecursiveCharacterTextSplitter(chunk_size = 500, chunk_overlap = 100)
        doc_splits = text_splitter.split_documents(documents=documents)
        return doc_splits
    
    def create_vectorstore(self):
        vectore_store = self.vectore_store
        doc_splits = self.get_data()
        vectore_store.add_documents(documents=doc_splits)
        

    def retrieve_documents(self, query: str) -> str:
            """
            Search for relevant documents in the knowledge base.
            
            Use this tool when you need information from the document collection
            to answer the user's question.
            """
            # Use MMR (Maximum Marginal Relevance) for diverse results
            retriever = self.vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 5, "fetch_k": 10}
            )
            
            # Retrieve documents
            results = retriever.invoke(query)
            
            if not results:
                return "No relevant documents found."
            
            # Format results
            formatted = "\n\n---\n\n".join(
                f"Document {i+1}:\n{doc.page_content}"
                for i, doc in enumerate(results)
            )
            
            return formatted


