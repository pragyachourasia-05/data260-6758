I used an AI assistant mainly to break the assignment requirements into smaller tasks, troubleshoot installation and coding problems, review my experimental setup, and improve the clarity of my report. I completed the implementation, downloaded and selected the corpus documents, configured the environment, ran the retrieval experiments, captured the screenshots, and reviewed the results myself.



One problem occurred during the first retrieval run. The script completed, but several retrieved text previews were unreadable because the PDF text extraction did not preserve the document content correctly. I identified the problem by inspecting the actual retrieved passages instead of relying only on the similarity scores and summary metrics. I then changed the extraction process to use PyMuPDF, limited the document text to a manageable size, and repeated the experiment. The second run produced readable previews and meaningful source comparisons, so I used those repeated results in this report and excluded the earlier faulty output.



