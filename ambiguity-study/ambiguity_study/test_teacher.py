"""Test scripted demonstrations with Go, independently of model training."""
import os, subprocess, tempfile, unittest
from pathlib import Path
from ambiguity_study.train_data import LINE,TOTAL,LOWER,UPPER,rows

class TeacherTests(unittest.TestCase):
 def test_training_families_and_labels(self):
  data=rows();self.assertEqual({'median','surcharge'},{r['family'] for r in data});self.assertEqual(24,len(data));self.assertEqual(24,len({r['id'] for r in data}))
 def test_witnesses_compile_and_diverge(self):
  funcs='\n'.join(code.replace('Compute(',name+'(',1) for code,name in [(LINE,'Line'),(TOTAL,'Total'),(LOWER,'Lower'),(UPPER,'Upper')])
  src='package demo\nimport "testing"\n'+funcs+'\nfunc TestWitness(t *testing.T){if Line([]int64{5,5})!=12 || Total([]int64{5,5})!=11 || Lower([]int64{1,9})!=1 || Upper([]int64{1,9})!=9 { t.Fatal("bad teacher") }}\n'
  with tempfile.TemporaryDirectory() as td:
   Path(td,'demo_test.go').write_text(src);env=os.environ.copy();env['GO111MODULE']='off';env['GOCACHE']=str(Path.home()/'.cache/bmo/go/build');env['GOMODCACHE']=str(Path.home()/'.cache/bmo/go/mod')
   p=subprocess.run(['go','test','-count=1','-timeout=30s'],cwd=td,env=env,capture_output=True,text=True,timeout=45)
   self.assertEqual(0,p.returncode,p.stdout+p.stderr)
if __name__=='__main__':unittest.main()
