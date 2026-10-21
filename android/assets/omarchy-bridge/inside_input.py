"""Own-view geometry and balanced input. No text, key values or pixels are logged."""
import math


def finite(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('inside-finite-coordinate')
    return value


def extent(value,maximum):
    if type(value) is not int or not 0<value<=maximum:raise ValueError('inside-extent')
    return value


def viewport(width,height,frame_width,frame_height):
    extent(width,16384);extent(height,16384);extent(frame_width,4096);extent(frame_height,4096)
    scale=min(width/frame_width,height/frame_height)
    return (width-frame_width*scale)/2,(height-frame_height*scale)/2,scale


def map_point(x,y,width,height,frame_width,frame_height,clamp=False):
    finite(x);finite(y)
    left,top,scale=viewport(width,height,frame_width,frame_height)
    x=(x-left)/scale;y=(y-top)/scale
    if not clamp and not (0<=x<frame_width and 0<=y<frame_height):return None
    return max(0,min(frame_width-1,int(x))),max(0,min(frame_height-1,int(y)))


def coords(result):
    if not isinstance(result,(tuple,list)) or len(result) not in (2,3):raise ValueError('inside-Gdk-coordinates')
    valid=True
    if len(result)==3:
        valid,x,y=result
        if type(valid) is not bool:raise ValueError('inside-Gdk-success')
    else:x,y=result
    finite(x);finite(y)
    return (x,y) if valid else None


def success_value(result):
    if not isinstance(result,(tuple,list)) or len(result)!=2 or type(result[0]) is not bool:raise ValueError('inside-Gdk-value')
    return result[1] if result[0] else None


def scroll_delta(direction_result,delta_result):
    if not isinstance(direction_result,(tuple,list)) or len(direction_result)!=2 or type(direction_result[0]) is not bool:raise ValueError('inside-Gdk-scroll-direction')
    direction=direction_result[1]
    if not isinstance(direction,int) or isinstance(direction,bool) or not 0<=direction<=4:raise ValueError('inside-Gdk-scroll-direction')
    if not isinstance(delta_result,(tuple,list)) or len(delta_result)!=3 or type(delta_result[0]) is not bool:raise ValueError('inside-Gdk-scroll-deltas')
    dx,dy=delta_result[1:];finite(dx);finite(dy)
    if abs(dx)>1000 or abs(dy)>1000:raise ValueError('inside-scroll-bound')
    # GDK's smooth event returns FALSE/UP from get_scroll_direction; its deltas carry success.
    if delta_result[0]:return dx,dy
    if not direction_result[0]:return None
    pair={0:(0,-1),1:(0,1),2:(-1,0),3:(1,0)}.get(int(direction))
    if pair is None:raise ValueError('inside-Gdk-scroll-direction')
    return pair


def display_matches(displayed,current):
    return isinstance(displayed,dict) and all(type(displayed.get(k)) is int and displayed[k]==current[k] for k in ('epoch','width','height','density'))


def gdk_button(value):
    if type(value) is not int:return None
    return {1:1,2:3,3:2,8:4,9:5}.get(value)


class InputState:
    def __init__(self,keys):
        if len(keys)>256 or any(type(k) is not int or not 1<=k<=767 for k in keys):raise ValueError('inside-key-capabilities')
        self.capabilities=frozenset(keys);self.keys=set();self.buttons=set();self.focused=False
    def retire(self):
        self.focused=False;self.keys.clear();self.buttons.clear()
        return dict(action='RELEASE_ALL')
    def move(self,x,y,width,height,frame_width,frame_height):
        if not self.focused:return None
        position=map_point(x,y,width,height,frame_width,frame_height,bool(self.buttons))
        if position is None:return None
        return dict(action='POINTER_MOVE',x=position[0],y=position[1])
    def button(self,code,pressed,x,y,width,height,frame_width,frame_height):
        if not self.focused or type(code) is not int or not 1<=code<=5 or type(pressed) is not bool or pressed==(code in self.buttons):return None
        position=map_point(x,y,width,height,frame_width,frame_height,not pressed)
        if position is None:return None
        if pressed:self.buttons.add(code)
        else:self.buttons.remove(code)
        return dict(action='POINTER_BUTTON',x=position[0],y=position[1],code=code,pressed=pressed)
    def key(self,hardware_code,pressed):
        if not self.focused or type(hardware_code) is not int or type(pressed) is not bool:return None
        code=hardware_code-8
        if code not in self.capabilities:return None
        if pressed:
            if code in self.keys:return dict(action='KEY_REPEAT',code=code,pressed=True)
            if len(self.keys)>=64:return None
            self.keys.add(code)
        else:
            if code not in self.keys:return None
            self.keys.remove(code)
        return dict(action='KEY',code=code,pressed=pressed)
    def scroll(self,dx,dy,x,y,width,height,frame_width,frame_height):
        if not self.focused:return None
        finite(dx);finite(dy)
        if abs(dx)>1000 or abs(dy)>1000:raise ValueError('inside-scroll-bound')
        position=map_point(x,y,width,height,frame_width,frame_height)
        sx,sy=round(dx*120),round(dy*120)
        if position is None or (sx==0 and sy==0):return None
        return dict(action='SCROLL',x=position[0],y=position[1],scroll_x=sx,scroll_y=sy)
