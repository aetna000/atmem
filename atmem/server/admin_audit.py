"""Content-free chained administrative audit."""
import hashlib, json, time
class AdminAudit:
    def __init__(self): self.rows=[]
    def append(self, principal_id, action, target_digest):
        previous=self.rows[-1]["digest"] if self.rows else "0"*64
        body={"principal_id":principal_id,"action":action,"target_digest":target_digest,"timestamp":time.time(),"previous":previous}
        body["digest"]=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest(); self.rows.append(body); return body
    def verify(self):
        previous="0"*64
        for row in self.rows:
            body={k:v for k,v in row.items() if k != "digest"}
            if body["previous"] != previous or hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=row["digest"]: return False
            previous=row["digest"]
        return True
