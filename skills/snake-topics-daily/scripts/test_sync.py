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
  for key,value in [('DOCS',self.docs),('INDEX',self.docs/'topic_photo_index.json'),('STATE',self.docs/'topic_sync_state.json'),('SPECIES_CATALOG',self.docs/'species_catalog.json')]:
   p=patch.object(m,key,value);p.start();self.stack.append(p)
  m.SPECIES_CATALOG.write_text(json.dumps({'schema_version':1,'total_species':2,'species':self.species}))
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
 def test_default_window_resumes_after_long_gap(self):
  m.STATE.write_text(json.dumps({'last_successful_cutoff':'2026-10-01T09:00:00+08:00'}))
  before=m.STATE.read_bytes();end=datetime.fromisoformat('2026-10-18T14:00:00+08:00')
  start,finish=m.incremental_window(end)
  self.assertEqual(start,datetime.fromisoformat('2026-10-01T01:00:00+00:00'))
  self.assertEqual(finish,end);self.assertEqual(m.STATE.read_bytes(),before)
 def test_missing_checkpoint_does_not_default_to_three_days(self):
  with self.assertRaises(RuntimeError):m.incremental_window()
 def test_future_checkpoint_rejected(self):
  m.STATE.write_text(json.dumps({'last_successful_cutoff':'2099-10-01T09:00:00+08:00'}))
  with self.assertRaises(RuntimeError):m.incremental_window(datetime.fromisoformat('2026-10-18T14:00:00+08:00'))
 def test_naive_checkpoint_rejected(self):
  m.STATE.write_text(json.dumps({'last_successful_cutoff':'2026-10-01T09:00:00'}))
  with self.assertRaises(RuntimeError):m.incremental_window()
 def test_retry_survives_after_checkpoint(self):
  retry=self.topic('old');retry['createTime']=10
  state={'retry_topics':[retry],'excluded_topic_ids':['rejected']}
  recent=self.topic('new',url='https://xstatic.pictureknow.com/new.png');recent['createTime']=200
  bad=self.topic('rejected');bad['createTime']=200
  result=m.review_candidates([recent,bad],datetime.fromtimestamp(100,timezone.utc),datetime.fromtimestamp(300,timezone.utc),state)
  self.assertEqual([x['uniqueId'] for x in result],['old','new'])
  self.assertTrue(all('visual_verified' not in x for x in result))
 def new_topic(self):
  topic=self.topic('new','c','https://xstatic.pictureknow.com/new.png')
  topic.update(sciName='Test nova',cnName='丙蛇',new_species={'verified':True,'site_id':'c','scientific_name':'Test nova','chinese_name':'丙蛇','source_url':'https://snake.pictureknow.com/snake?id=c'})
  return topic
 def test_new_species_extends_152_without_duplicate_folder(self):
  import string
  catalog=list(self.species)
  for i in range(150):
   latin='Seed'+string.ascii_lowercase[i//26]+string.ascii_lowercase[i%26]+' species'
   catalog.append(dict(site_id=f'seed{i}',scientific_name=latin,chinese_name=f'种{i}',toxicity='无毒',folder=latin+f'--种{i}--无毒'))
  m.SPECIES_CATALOG.write_text(json.dumps({'total_species':152,'species':catalog}))
  with patch.object(m,'request_bytes',return_value=(self.blob,'image/png')):
   self.assertEqual(m.archive_topics([self.new_topic()],''),(1,1))
   self.assertEqual(m.archive_topics([self.new_topic()],''),(0,1))
  after=json.loads(m.SPECIES_CATALOG.read_text())
  self.assertEqual(after['total_species'],153);self.assertEqual(len(after['species']),153)
  folder=self.docs/'photos/Test nova--丙蛇--毒性待核实'
  self.assertTrue((folder/'.gitkeep').exists());self.assertEqual(len(list(folder.glob('*.png'))),1)
  self.assertFalse(m.STATE.exists())
 def test_unverified_species_does_not_create_folder(self):
  topic=self.new_topic();topic['new_species']['verified']=False
  with patch.object(m,'request_bytes') as fetch:
   self.assertEqual(m.archive_topics([topic],''),(0,0));fetch.assert_not_called()
  self.assertEqual(len(m.load_species_catalog()),2)
 def test_new_site_id_with_existing_scientific_name_reuses_species(self):
  topic=self.new_topic();topic.update(sciName='Test a',cnName='甲蛇')
  with patch.object(m,'request_bytes',return_value=(self.blob,'image/png')):m.archive_topics([topic],'')
  self.assertEqual(len(m.load_species_catalog()),2)
  self.assertTrue(m.load_index(m.INDEX)['photos'][0]['path'].startswith('photos/Test a--'))
 def test_new_species_cannot_override_conflicting_existing_labels(self):
  topic=self.new_topic();topic['cnName']='乙蛇';topic['new_species']['chinese_name']='乙蛇'
  with patch.object(m,'request_bytes') as fetch:
   self.assertEqual(m.archive_topics([topic],''),(0,0));fetch.assert_not_called()
  self.assertEqual(len(m.load_species_catalog()),2)
 def test_unsafe_new_species_folder_rejected(self):
  topic=self.new_topic();topic['cnName']='../丙蛇';topic['new_species']['chinese_name']='../丙蛇'
  with patch.object(m,'request_bytes') as fetch:
   self.assertEqual(m.archive_topics([topic],''),(0,0));fetch.assert_not_called()
 def test_failed_download_does_not_persist_new_species(self):
  before=m.SPECIES_CATALOG.read_bytes()
  with patch.object(m,'request_bytes',side_effect=RuntimeError('download failed')):
   with self.assertRaises(RuntimeError):m.archive_topics([self.new_topic()],'')
  self.assertEqual(m.SPECIES_CATALOG.read_bytes(),before)
if __name__=='__main__':unittest.main(verbosity=2)
