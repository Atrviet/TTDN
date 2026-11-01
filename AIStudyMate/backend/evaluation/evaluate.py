from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT=Path(__file__).parent
def ratio(ok,total):return round(ok/total,4) if total else None
def evaluate(data:dict[str,Any])->dict[str,Any]:
    retrieval=sum(bool(set(c["expected_pages"])&set(c["retrieved_pages"])) for c in data["retrieval_cases"])
    citations=sum(set(c["cited_pages"])<=set(c["expected_pages"]) and bool(c["cited_pages"]) for c in data["citation_cases"])
    flash=sum(c["expected_answer"].casefold() in c["actual_answer"].casefold() and c["source_page"]==c["expected_page"] for c in data["flashcard_cases"])
    tutor=sum(all(claim.casefold() in c["evidence"].casefold() for claim in c["claims"]) for c in data["tutor_cases"])
    schedules=0
    for case in data["schedule_cases"]:
        daily={};intervals=[];valid=True;exam=datetime.fromisoformat(case["exam_date"]).date()
        for task in case["tasks"]:
            start=datetime.fromisoformat(task["start"]);end=start.timestamp()+task["duration"]*60
            valid &= start.date()<=exam and start.weekday() in case["allowed_weekdays"]
            daily[start.date()]=daily.get(start.date(),0)+task["duration"]
            valid &= daily[start.date()]<=case["daily_minutes"] and all(end<=s or start.timestamp()>=e for s,e in intervals);intervals.append((start.timestamp(),end))
        schedules+=bool(valid)
    tp=fp=fn=0
    for case in data["knowledge_graph_cases"]:
        expected={tuple(x) for x in case["expected_relations"]};predicted={tuple(x) for x in case["predicted_relations"]};tp+=len(expected&predicted);fp+=len(predicted-expected);fn+=len(expected-predicted)
    kg_f1=ratio(2*tp,2*tp+fp+fn)
    quiz=sum(c["selected"]==c["expected"] for c in data["quiz_cases"])
    consistent=0
    for c in data["weakness_cases"]:
        scores={"quiz":c["quiz_score"],"flashcard":c["flashcard_score"],"practice":c["practice_score"]};available={k:v for k,v in scores.items() if v is not None};total=sum(c["weights"][k] for k in available);actual=sum(v*c["weights"][k]/total for k,v in available.items());consistent+=abs(actual-c["expected_mastery"])<1e-6
    return {"dataset":{"documents":len(data["documents"]),"pages":sum(d["pages"] for d in data["documents"]),"retrieval_cases":len(data["retrieval_cases"]),"flashcard_cases":len(data["flashcard_cases"]),"tutor_cases":len(data["tutor_cases"]),"schedule_cases":len(data["schedule_cases"]),"knowledge_graph_cases":len(data["knowledge_graph_cases"]),"quiz_cases":len(data["quiz_cases"]),"weakness_cases":len(data["weakness_cases"])},"metrics":{"rag_retrieval_page_hit_rate":ratio(retrieval,len(data["retrieval_cases"])),"citation_page_correctness":ratio(citations,len(data["citation_cases"])),"flashcard_reference_accuracy":ratio(flash,len(data["flashcard_cases"])),"tutor_claim_groundedness":ratio(tutor,len(data["tutor_cases"])),"schedule_constraint_pass_rate":ratio(schedules,len(data["schedule_cases"])),"knowledge_relation_f1":kg_f1,"quiz_reference_accuracy":ratio(quiz,len(data["quiz_cases"])),"weakness_formula_consistency":ratio(consistent,len(data["weakness_cases"]))}}
if __name__=="__main__":print(json.dumps(evaluate(json.loads((ROOT/"advanced_learning_dataset.json").read_text())),ensure_ascii=False,indent=2))
