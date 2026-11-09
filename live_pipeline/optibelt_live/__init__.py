"""Hardware-independent experimental OPTIBELT streaming pipeline."""
import os,sys
from pathlib import Path
PROJECT=Path(os.environ.get('OPTIBELT_PROJECT',str(Path(__file__).resolve().parents[2]))).resolve()
sys.path.insert(0,str(PROJECT/'src'))
