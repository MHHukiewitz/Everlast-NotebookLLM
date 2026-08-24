# KI-Wissensdatenbank: Architektur in sechs Schichten

Eine KI-Wissensdatenbank verbindet Unternehmensdokumente mit Sprachmodellen. Everlast AI beschreibt sechs Schichten.

## Schicht 1: Ingest
Der Ingest-Layer holt PDF, Word, HTML, Markdown und CSV. Metadaten wie Quelle, Autor, Datum und Vertraulichkeit werden gespeichert.

## Schicht 2: Embeddings
Dokumente werden in Chunks zerlegt. Embeddings landen in einer Vektor-Datenbank. Für den Start reicht pgvector. Die Vektoren bleiben im Haus.

## Schicht 3: Retrieval
Reine Vektorsuche verfehlt Produktnummern, Paragraphen und Eigennamen. Deshalb kombinieren wir Dense-Retrieval mit BM25. Das heißt Hybrid-Search. Ein Re-Ranker sortiert die Top-Treffer neu.

## Schicht 4: Modell
Wer maximale Datenhoheit will, betreibt lokale Modelle über Ollama, vLLM oder TGI. Cloud-Modelle dürfen nur Frage plus relevante Chunks sehen. Die Vektoren bleiben lokal.

## Schicht 5: Permissions und Monitoring
Jeder Chunk trägt Berechtigungen. Auditing speichert Quelle, Modell und Version. Auditing löscht keine Daten.

Eine Löschanfrage muss die Quelle und den Vektor-Index entfernen. Das Dokument und die Embeddings werden zusammen gelöscht.

## Schicht 6: Agenten
Agenten brauchen klare Fähigkeiten mit Eingabe- und Ausgabe-Schemata.

## Beobachtung
Langfuse speichert Traces, Kosten und Qualität jedes Modellaufrufs. Langfuse kann selbst gehostet werden.
