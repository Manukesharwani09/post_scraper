import nltk
from collections import Counter
import re
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

def pubmed_extract_tags(text, max_tags=5):
    # simple consecutive noun chunking
    words = nltk.word_tokenize(text)
    tags = nltk.pos_tag(words)
    
    phrases = []
    current_phrase = []
    for word, pos in tags:
        if pos.startswith('NN') or pos.startswith('JJ'):
            current_phrase.append(word)
        else:
            if current_phrase:
                phrases.append(" ".join(current_phrase))
                current_phrase = []
    if current_phrase:
         phrases.append(" ".join(current_phrase))
         
    # filter generic
    ignore = {"research", "study", "findings", "methods", "healthcare"}
    
    clean = []
    for p in phrases:
        p_clean = re.sub(r'[^A-Za-z0-9\-\s]', '', p).strip()
        if len(p_clean) > 2 and p_clean.lower() not in ignore: # keep interesting
            # title-case if lowercase, else keep if has upper
            if p_clean.islower(): p_clean = p_clean.title()
            clean.append(p_clean)
            
    # get most common
    freq = Counter(clean)
    final = []
    for k, v in freq.most_common(max_tags * 2):
        if len(final) >= max_tags: break
        # duplicate removal case-insensitive
        if not any(k.lower() in existing.lower() or existing.lower() in k.lower() for existing in final):
            final.append(k)
            
    return final

print(pubmed_extract_tags("Growth differentiation factor 11 (GDF11) and myostatin (MSTN) are closely related TGFβ family members that are often believed to serve similar functions due to their high homology. However, genetic studies in animals provide clear evidence that they perform distinct roles. While the loss of Mstn leads to hypermuscularity, the deletion of Gdf11 results in abnormal skeletal patterning and organ development. The perinatal lethality of Gdf11-null mice, which contrasts with the long-term viability of Mstn-null mice, has led most research to focus on utilizing recombinant GDF11 proteins to investigate the postnatal functions of GDF11. However, the reported outcomes of the exogenous application of recombinant GDF11 proteins are controversial partly because of the different sources and qualities of recombinant GDF11 used and because recombinant GDF11 and MSTN proteins are nearly indistinguishable due to their similar structural and biochemical properties. Here, we analyze the similarities and differences between GDF11 and MSTN from an evolutionary point of view and summarize the current understanding of the biological processing, signaling, and physiological functions of GDF11 and MSTN. Finally, we discuss the potential use of recombinant GDF11 as a therapeutic option for a wide range of medical conditions and the possible adverse effects of GDF11 inhibition mediated by MSTN inhibitors."))
