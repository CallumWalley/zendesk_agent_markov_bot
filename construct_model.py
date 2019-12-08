import cProfile
from zenpy import Zenpy
import markovify as mk
import datetime as dt
import multiprocessing as mp
import json, time, difflib, math, re, spacy, functools, sys

# Load natural lanuage proccessor.
nlp = spacy.load('en_core_web_sm')

with open("default_inputs.json", "r") as f:
    default_inputs=json.load(f)

with open("zendesk_credentials.json", "r") as f:
    zendesk_credentials=json.load(f)
zenpy_client = Zenpy(**zendesk_credentials)

for inparg in sys.argv:
    keypair=inparg.split("=")
    if len(keypair)==2:
        keypair[0]=keypair[0].strip().lower()
        if keypair[0] in default_inputs.keys():
            default_inputs[keypair[0]]=keypair[1].strip().lower()    

def get_flavor(input_string):
    all_agents={}
    flav_agent_ids=[]
    flav_agent_names=[]

    # Get list of all agents.
    try:
        for user in zenpy_client.users(role="agent"):
            all_agents[user.name]=user.id
    except:
        all_agents=default_inputs["all_agents"]
    else:
        default_inputs["all_agents"]=all_agents
        with open("default_inputs.json", "w") as f:
            f.write(json.dumps(default_inputs))

    flav_list=input_string.split(",")

    for flav in flav_list:   
        fuz_match=difflib.get_close_matches(flav.strip().capitalize(), all_agents, n=1, cutoff=0.2)
        if len(fuz_match)>0 and not all_agents[fuz_match[0]] in flav_agent_ids:
            flav_agent_names.append(fuz_match[0])
            flav_agent_ids.append(all_agents[fuz_match[0]])

    flav_agent_names.sort()
    if len(flav_agent_ids)>0:
        print("Using agent/s " + " and ".join(flav_agent_names) + " as flavor.")

        corpus_name_list={}
        lfan=len(flav_agent_names)
        x=0
        for fullname in flav_agent_names:
            i=0
            for name in fullname.split():
                if not i in corpus_name_list:
                    corpus_name_list[i]=""
                corpus_name_list[i]+=name[(math.floor((len(name)/lfan)*x)):(math.ceil((len(name)/lfan)*(x+1)))].lower()
                i+=1
            x+=1
        map(str.capitalize, corpus_name_list.values())
        corpus_name = "_".join(corpus_name_list.values())
    else:
        flav_agent_ids=all_agents.values()
        print("No agent filter")

        corpus_name="bap_cmd"
    corpus_name=("state"+str(default_inputs["state_size"])+"_"+corpus_name)
    return flav_agent_ids, corpus_name

class POSifiedText(mk.Text):
    def word_split(self, sentence):
        return ["::".join((word.orth_, word.pos_)) for word in nlp(sentence)]

    def word_join(self, words):
        sentence = " ".join(word.split("::")[0] for word in words)
        return sentence
    
    # Custom delimit by carrage return.
    def sentence_split(self, text):
        return re.split(r"\s*\r\s*", text)

def build_corpus(agent_ids):
    parpool = mp.Pool() # Create a multiprocessing Pool
    
    print("Building corpus... build period " + str(default_inputs["max_build_period"]) + " days.")
    # Agent Ids static. Build partial func
    batch_partial=functools.partial(batch_period, agent_ids=tuple(agent_ids), state_size=int(default_inputs["state_size"])) 

    # Search API can only handle 1000 replies. # Split into multiple requests 10 days.  
    num_iters=math.ceil(int(default_inputs["max_build_period"])/10)
    model_list=parpool.map(batch_partial, range(0,num_iters))
    print("All reference data indexed.")
    
    print("Combining models...")
    # Filter out nones and combine.
    combined_models=mk.combine(models=list(filter(None, model_list)))
    return combined_models

def batch_period(batch, agent_ids, state_size):
    this_proc=mp.current_process().name
    batch_corpus=""
    ingested_words=0
    window_end = dt.datetime.now() - dt.timedelta(days=(batch)*10)
    window_start = window_end - dt.timedelta(days=10)
    print( this_proc + " fetching period " + window_start.strftime("%Y-%m-%d") + " to " + window_end.strftime("%Y-%m-%d"))
    ticket_chunk=zenpy_client.search(" ".join("commenter:"+str(x) for x in agent_ids), type='ticket', created_between=[window_start, window_end], sort_by='created_at', sort_order='desc')
    if not ticket_chunk.count:
        return None
    for ticket_no in ticket_chunk:
        for comment in zenpy_client.tickets.comments(ticket=ticket_no.id):
            if comment.author.id in agent_ids:
                ingested_words+=len(comment.body.split())
                # Using carrage return to represent end of comment.
                batch_corpus += comment.body + "\r"    
    #print(batch_corpus)
    model=POSifiedText(batch_corpus + "\r", well_formed=False, state_size=(state_size))
    print("\r" + this_proc + " " + str(ingested_words) + " words ingested.")

    return model

def main():
    print("Using..")
    for key, value in default_inputs.items():
        if key != "all_agents":
            print(key + " = " + str(value))

    [agent_ids, corpus_name]=get_flavor(default_inputs["flavor"])
    try:
        if not default_inputs["use_cache"]:
            raise Exception("Cache disabled")
        with open("corpus_cache/" + corpus_name + ".json") as f:
            model=POSifiedText.from_json(f.read())
            print("Loaded '" + corpus_name + "'")
        new_corpus=False 
    except Exception as thing:
        print("No existing corpus: " + str(thing))
        print("Building new corpus '" + corpus_name + "'")
        new_corpus=True
        model=build_corpus(agent_ids)
        
    if new_corpus and default_inputs["make_cache"]:
        print("Saving '" + corpus_name + "' to cache")
        with open("corpus_cache/" + corpus_name + ".json", "w+") as f:
            f.write(model.to_json())
    while 1:
        input("\rPress Enter.")
        print(model.make_sentence(strict=False, tries=50))

if __name__ == '__main__':
    main()
