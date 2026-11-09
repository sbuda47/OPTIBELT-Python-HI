from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated,Literal
from fastapi import FastAPI,HTTPException,Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,StrictInt,ConfigDict
from . import service

@asynccontextmanager
async def lifespan(app):
    # Fresh checkouts can serve the UI before authorized reproduction data is supplied.
    try:service.snapshot()
    except service.SourceUnavailable:pass
    yield

app=FastAPI(title='OPTIBELT recorded playback',version='0.1.0',lifespan=lifespan)

class PlaybackRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reference:Literal['C','A']='C'
    duration:Literal[2,3,5]=3
    acknowledgements:list[Annotated[StrictInt,Field(ge=0)]]=Field(default_factory=list,max_length=100)

class SpectrumRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['fft','envelope']='fft'
    start:Annotated[float,Field(ge=0,allow_inf_nan=False)]=0
    seconds:Literal[2,5,10]=2
    low:Annotated[float|None,Field(ge=10,lt=12800,allow_inf_nan=False)]=None
    high:Annotated[float|None,Field(gt=10,lt=12800,allow_inf_nan=False)]=None

def call(fn,*args):
    try:return fn(*args)
    except service.SourceUnavailable as exc:raise HTTPException(503,str(exc)) from exc
    except KeyError as exc:raise HTTPException(404,str(exc)) from exc
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    except OSError as exc:raise HTTPException(503,'Source data could not be read.') from exc

@app.get('/api/health')
def health():return {'status':'ok','application':'optibelt-web-dashboard'}

@app.get('/api/catalog')
def catalog():return call(service.catalogue)

@app.get('/api/recordings/{recording_id}/playback')
def playback(recording_id:str,reference:Literal['C','A']='C',duration:Literal['2','3','5']='3'):
    return call(service.playback,recording_id,reference,int(duration))

@app.post('/api/recordings/{recording_id}/playback')
def acknowledged_playback(recording_id:str,request:PlaybackRequest):
    return call(service.playback,recording_id,request.reference,request.duration,request.acknowledgements)

@app.get('/api/recordings/{recording_id}/signal')
def signal(recording_id:str,channel:Literal['vibration','torque','current_r','current_s','current_t']='vibration',
           start:Annotated[float,Query(ge=0,allow_inf_nan=False)]=0,
           seconds:Annotated[float,Query(ge=.00001,le=2,allow_inf_nan=False)]=.1,
           smooth_ms:Annotated[float|None,Query(ge=.01,le=100,allow_inf_nan=False)]=None):
    return call(service.signal,recording_id,channel,start,seconds,smooth_ms)

@app.post('/api/recordings/{recording_id}/spectrum')
def spectrum(recording_id:str,request:SpectrumRequest):
    return call(service.spectrum,recording_id,request.mode,request.start,request.seconds,request.low,request.high)

DIST=Path(__file__).resolve().parents[1]/'dist'
if DIST.is_dir():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')

@app.get('/',include_in_schema=False)
def index():
    if not (DIST/'index.html').is_file():raise HTTPException(503,'Build the frontend with npm run build first.')
    return FileResponse(DIST/'index.html')
