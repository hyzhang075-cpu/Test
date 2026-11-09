import pickle,numpy as np
from pathlib import Path
class Reader(pickle.Unpickler):
 def find_class(self,module,name):
  allowed={('numpy','ndarray'),('numpy','dtype'),('numpy.core.multiarray','_reconstruct'),('numpy.core.multiarray','scalar'),('numpy._core.multiarray','_reconstruct'),('numpy._core.multiarray','scalar'),('numpy.core.numeric','_frombuffer'),('numpy._core.numeric','_frombuffer')}
  if (module,name) not in allowed:raise ValueError(f'Unsupported pickle class: {module}.{name}')
  return super().find_class(module,name)
frames=[]
with open('C:/Users/hyzha/Downloads/VTK_ShapeData_20261106_112516.pkl','rb') as f:
 while True:
  try:frames.append(Reader(f).load())
  except EOFError:break
print('frames',len(frames));print('keys',list(frames[0]));print({k:(type(v).__name__,np.shape(v)) for k,v in frames[0].items()});print('time',frames[0]['timestamp'],frames[-1]['timestamp']);print('rawfirst',str(frames[0]['raw_data'])[:300])
np.savez_compressed('docs/09B7_dynamic_112516_arrays.npz',raw_data=np.asarray([v['raw_data'] for v in frames]),magnitude=np.asarray([v['magnitude'] for v in frames]),angle=np.asarray([v['angle'] for v in frames]),timestamp=np.asarray([v['timestamp'] for v in frames]))
