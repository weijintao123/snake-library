"""Offline behavioral checks; no live credentials or external writes."""
import importlib.util,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
from PIL import Image
spec=importlib.util.spec_from_file_location('snake_sync',Path(__file__).resolve().parents[1]/'assets/sync_catalog.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SyncTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.docs=self.root/'docs';self.docs.mkdir()
  self.species=[dict(site_id='a',scientific_name='Test a',chinese_name='甲蛇',toxicity='无毒',folder='Test a--甲蛇--无毒'),dict(site_id='b',scientific_name='Test b',chinese_name='乙蛇',toxicity='无毒',folder='Test b--乙蛇--无毒')]
  stream=io.BytesIO();Image.new('RGB',(9,9),'red').save(stream,format='PNG');self.blob=stream.getvalue()
  self.stack=[]
  for key,value in [('DOCS',self.docs),('INDEX',self.docs/'topic_photo_index.json'),('STATE',self.docs/'topic_sync_state.json')]:
   p=patch.object(m,key,value);p.start();self.stack.append(p)
  p=patch.object(m,'load_species_catalog',return_value=self.species);p.start();self.stack.append(p)
 def tearDown(self):
  for p in reversed(self.stack):p.stop()
  self.tmp.cleanup()
 def topic(self,id='1',species='a',url='https://xstatic.pictureknow.com/snake/one.png'):
  return dict(uniqueId=id,snakeId=species,img=url,createTime=1792299771000,visual_verified=True)
 def test_requires_visual_review(self):
  topic=self.topic();topic.pop('visual_verified')
  with patch.object(m,'request_bytes') as fetch:
   self.assertEqual(m.archive_topics([topic],''),(0,0));fetch.assert_not_called()
 def test_idempotent_url(self):
  with patch.object(m,'request_bytes',return_value=(self.blob,'image/jpeg')) as fetch:
   self.assertEqual(m.archive_topics([self.topic()],''),(1,1));self.assertEqual(m.archive_topics([self.topic()],''),(0,1));self.assertEqual(fetch.call_count,1)
  photo=m.load_index(m.INDEX)['photos'][0];self.assertTrue(photo['path'].endswith('.png'));self.assertEqual((self.docs/photo['path']).read_bytes(),self.blob)
 def test_cross_species_duplicate_has_one_file(self):
  with patch.object(m,'request_bytes',return_value=(self.blob,'image/png')):
   self.assertEqual(m.archive_topics([self.topic(),self.topic('2','b','https://xstatic.pictureknow.com/snake/two.png')],''),(1,1))
  self.assertEqual(len(list(self.docs.rglob('*.png'))),1)
 def test_conflicting_labels_rejected(self):
  topic=self.topic();topic['cnName']='乙蛇';self.assertIsNone(m.match_species(topic,self.species))
 def test_known_url_repairs_mirror(self):
  with patch.object(m,'request_bytes',return_value=(self.blob,'image/png')):
   m.archive_topics([self.topic()],'')
   with patch.dict(m.os.environ,{'SNAKE_LOCAL_PHOTO_ROOT':str(self.root/'mirror')}):self.assertEqual(m.archive_topics([self.topic()],''),(0,1))
  self.assertEqual(len(list((self.root/'mirror').rglob('*.png'))),1)
 def test_pagination_covers_start(self):
  start=datetime.fromtimestamp(100,tz=timezone.utc)
  with patch.object(m,'fetch_page',side_effect=[{'total':20000,'pages':[dict(uniqueId='a',createTime=200000)]},{'total':20000,'pages':[dict(uniqueId='b',createTime=50)]}]) as fetch:
   self.assertEqual(len(m.collect_topics('',start)),2);self.assertEqual(fetch.call_count,2)
 def test_pagination_repeated_page_fails(self):
  with patch.object(m,'fetch_page',return_value={'total':20000,'pages':[dict(uniqueId='a',createTime=200)]}):
   with self.assertRaises(RuntimeError):m.collect_topics('',datetime.fromtimestamp(100,tz=timezone.utc))
if __name__=='__main__':unittest.main(verbosity=2)
