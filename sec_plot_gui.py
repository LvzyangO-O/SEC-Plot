"""Standalone interactive AKTA/UNICORN SEC plotter. Run: py sec_plot_gui.py"""
from __future__ import annotations
import csv, re, ctypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MultipleLocator
import numpy as np

def enable_high_dpi():
    """Ask Windows for native-resolution rendering before Tk is created."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try: ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass

def num(x):
    try: return float(x.strip())
    except (ValueError, AttributeError): return None

def read_akta(path):
    """Find UV and Fraction blocks from their labels in metadata row 2."""
    with Path(path).open(newline="", encoding="utf-8-sig") as f: rows=list(csv.reader(f))
    if len(rows)<4: raise ValueError("CSV 文件没有足够的数据行。")
    tags=[x.strip().lower() for x in rows[1]]
    try: u=next(i for i,x in enumerate(tags) if x=="uv"); q=next(i for i,x in enumerate(tags) if x=="fraction")
    except StopIteration: raise ValueError("CSV 第二行未找到 UV 或 Fraction 标记。")
    xs=[]; ys=[]; starts=[]
    for r in rows[3:]:
        r += [""]*max(0,max(u,q)+2-len(r)); x,y=num(r[u]),num(r[u+1]); v,name=num(r[q]),r[q+1].strip()
        if x is not None and y is not None: xs.append(x); ys.append(y)
        if v is not None and name: starts.append((name,v))
    if not xs or not starts: raise ValueError("未读取到 UV 或 Fraction 数据。")
    ds=np.diff([v for _,v in starts]); end=float(np.median(ds[ds>0])) if np.any(ds>0) else .2
    bounds={n:(v,starts[i+1][1] if i+1<len(starts) else v+end) for i,(n,v) in enumerate(starts)}
    return np.asarray(xs),np.asarray(ys),bounds

def val(s, name):
    if not s.strip(): return None
    try: return float(s)
    except ValueError: raise ValueError(f"{name} 必须是数字。")

def volume_ranges(text):
    """Parse volume ranges such as: 8-10, 12.5-13.2."""
    answer=[]
    pattern=re.compile(r"^\s*([+]?(?:\d+(?:\.\d*)?|\.\d+))\s*[-–—:]\s*([+]?(?:\d+(?:\.\d*)?|\.\d+))\s*$")
    for item in text.replace("，",",").split(","):
        if not item.strip():continue
        m=pattern.match(item)
        if not m:raise ValueError("洗脱体积格式应为 8-10, 12.5-13.2。")
        start,stop=map(float,m.groups())
        if start>=stop:raise ValueError("填充体积的起点必须小于终点。")
        answer.append((start,stop))
    return answer

class Plate(tk.Toplevel):
    pat=re.compile(r"^(\d+)\.([A-H])\.(\d+)$")
    def __init__(self, master,path,old):
        super().__init__(master); self.result=None; self.title("选择填充孔位")
        try: _,_,b=read_akta(path)
        except Exception as e: messagebox.showerror("无法读取",str(e),parent=self); self.destroy(); return
        wells={};
        for n in b:
            m=self.pat.match(n)
            if m: wells[(m[1],m[2],int(m[3]))]=n
        if not wells: messagebox.showerror("无孔位","找不到类似 6.A.1 的 Fraction。",parent=self);self.destroy();return
        self.vars={n:tk.BooleanVar(value=n in old) for n in wells.values()}
        ttk.Label(self,text="勾选要填充的收集孔位。",padding=8).pack(anchor="w")
        h=ttk.Frame(self,padding=8);h.pack()
        for plate in sorted({k[0] for k in wells},key=int):
            box=ttk.LabelFrame(h,text=f"Plate {plate}",padding=5);box.pack(side="left",padx=4)
            for c in range(1,13):ttk.Label(box,text=c,width=3,anchor="center").grid(row=0,column=c)
            for ri,r in enumerate("ABCDEFGH",1):
                ttk.Label(box,text=r).grid(row=ri,column=0)
                for c in range(1,13):
                    n=wells.get((plate,r,c))
                    if n:ttk.Checkbutton(box,variable=self.vars[n]).grid(row=ri,column=c)
        f=ttk.Frame(self,padding=8);f.pack(fill="x")
        ttk.Button(f,text="全选",command=lambda:[x.set(True) for x in self.vars.values()]).pack(side="left")
        ttk.Button(f,text="清空",command=lambda:[x.set(False) for x in self.vars.values()]).pack(side="left",padx=4)
        ttk.Button(f,text="确定",command=self.ok).pack(side="right");self.transient(master);self.grab_set()
    def ok(self):self.result=[n for n,x in self.vars.items() if x.get()];self.destroy()

class Row:
    def __init__(self,parent,remove,changed):
        self.f=ttk.LabelFrame(parent,text="曲线");self.remove=remove;self.changed=changed;self.path=tk.StringVar();self.label=tk.StringVar(value="Sample");self.color=tk.StringVar(value="#1464F4");self.volumes=tk.StringVar();self.wells=[]
        ttk.Label(self.f,text="CSV").grid(row=0,column=0,padx=4,pady=2);ttk.Entry(self.f,textvariable=self.path).grid(row=0,column=1,columnspan=3,sticky="ew");ttk.Button(self.f,text="选择…",command=self.choose).grid(row=0,column=4,padx=3);ttk.Button(self.f,text="删除",command=lambda:remove(self)).grid(row=0,column=5,padx=(0,3))
        ttk.Label(self.f,text="名称").grid(row=1,column=0,padx=4,pady=2);ttk.Entry(self.f,textvariable=self.label,width=18).grid(row=1,column=1,sticky="ew");ttk.Label(self.f,text="颜色").grid(row=1,column=2,padx=(7,2));ttk.Entry(self.f,textvariable=self.color,width=9).grid(row=1,column=3,sticky="ew");ttk.Button(self.f,text="选色",command=self.pick_color).grid(row=1,column=4,padx=3)
        self.well_button=ttk.Button(self.f,text="选择孔位…（0 孔）",width=18,command=self.pick_wells);self.well_button.grid(row=2,column=0,columnspan=2,sticky="w",padx=4,pady=2)
        ttk.Label(self.f,text="体积填充").grid(row=2,column=2,padx=(7,2));ttk.Entry(self.f,textvariable=self.volumes,width=18).grid(row=2,column=3,columnspan=2,sticky="ew");ttk.Label(self.f,text="例 8-10",foreground="#555").grid(row=2,column=5,sticky="w",padx=3)
        self.f.columnconfigure(1,weight=2);self.f.columnconfigure(3,weight=1)
        for v in (self.path,self.label,self.color,self.volumes):v.trace_add("write",lambda *_:self.changed())
    def choose(self):
        p=filedialog.askopenfilename(filetypes=[("CSV","*.csv"),("All files","*.*")])
        if p:self.set_file(p)
    def set_file(self,p,color=None):
        self.path.set(p);self.label.set(Path(p).stem);self.wells=[];self.show()
        if color:self.color.set(color)
    def pick_color(self):
        c=colorchooser.askcolor(color=self.color.get())[1]
        if c:self.color.set(c)
    def pick_wells(self):
        if not self.path.get():messagebox.showinfo("提示","请先选择 CSV。",parent=self.f);return
        d=Plate(self.f,self.path.get(),set(self.wells));self.f.wait_window(d)
        if d.result is not None:self.wells=d.result;self.show();self.changed()
    def show(self):self.well_button.config(text=f"选择孔位…（{len(self.wells)} 孔）")
    def spec(self):
        if not self.path.get():raise ValueError("请为每条曲线选择 CSV 文件。")
        return self.path.get(),self.label.get() or Path(self.path.get()).stem,self.color.get(),self.wells,volume_ranges(self.volumes.get())

class App(tk.Tk):
    def __init__(self):
        super().__init__();self.title("SEC 曲线绘图工具");self.rows=[];self.canvas=None;self.fig=None;self.preview_job=None
        self.screen_dpi=float(self.winfo_fpixels("1i"));self.tk.call("tk","scaling",max(1.0,self.screen_dpi/72.0));style=ttk.Style(self);style.configure(".",font=("Microsoft YaHei UI",10));style.configure("TButton",padding=(7,4))
        sw,sh=self.winfo_screenwidth(),self.winfo_screenheight();ww,wh=int(sw*.68),int(sh*.78);self.geometry(f"{ww}x{wh}+{(sw-ww)//2}+{(sh-wh)//2}");self.minsize(1050,700)
        self.panes=ttk.Panedwindow(self,orient="horizontal");self.panes.pack(fill="both",expand=True)
        l=ttk.Frame(self.panes,padding=10);self.preview=ttk.LabelFrame(self.panes,text="预览",padding=4);self.panes.add(l,weight=0);self.panes.add(self.preview,weight=1);self.after_idle(lambda:self.panes.sashpos(0,int(self.winfo_width()*.46)))
        ttk.Label(l,text="数据",font=("Microsoft YaHei UI",12,"bold")).pack(anchor="w")
        data=ttk.Frame(l);data.pack(fill="x");self.data_canvas=tk.Canvas(data,width=650,height=135,highlightthickness=0);scroll=ttk.Scrollbar(data,orient="vertical",command=self.data_canvas.yview);self.data_canvas.configure(yscrollcommand=scroll.set);self.data_canvas.pack(side="left",fill="x",expand=True);scroll.pack(side="right",fill="y");self.rowbox=ttk.Frame(self.data_canvas);self.row_window=self.data_canvas.create_window((0,0),window=self.rowbox,anchor="nw");self.rowbox.bind("<Configure>",self.resize_curve_area);self.data_canvas.bind("<Configure>",lambda e:self.data_canvas.itemconfigure(self.row_window,width=e.width))
        self.add();data_buttons=ttk.Frame(l);data_buttons.pack(anchor="w",pady=4);ttk.Button(data_buttons,text="+ 添加空白曲线",command=self.add).pack(side="left");ttk.Button(data_buttons,text="批量导入 CSV…",command=self.batch_add).pack(side="left",padx=5)
        b=ttk.LabelFrame(l,text="图形设置",padding=7);b.pack(fill="x")
        d={"title":"","xlabel":"Elution volume (mL)","ylabel":"UV absorbance (mAU)","titlex":"0.5","titley":"1.02","xlabelpos":"居中","ylabelpos":"居中","xlabelpad":"8","ylabelpad":"8","xmin":"","xmax":"","ymin":"","ymax":"","xmajor":"","ymajor":"","xminor":"","yminor":"","font":"Arial","ticksize":"11","titlesize":"14","axissize":"12","titlebold":"0","axisbold":"0","legend":"右上","legendx":"","legendy":"","w":"18.8","h":"12.2","dpi":"450","transparent":"0"};self.v={k:tk.StringVar(value=x) for k,x in d.items()}
        sizes=["8","9","10","11","12","14","16","18","20","22","24"]
        for r,(lab,k) in enumerate([("标题","title"),("X 轴标题","xlabel"),("Y 轴标题","ylabel")]):ttk.Label(b,text=lab).grid(row=r,column=0,sticky="w",pady=2);ttk.Entry(b,textvariable=self.v[k],width=27).grid(row=r,column=1,columnspan=2,sticky="ew")
        ttk.Label(b,text="标题 X / Y").grid(row=3,column=0,sticky="w");ttk.Entry(b,textvariable=self.v["titlex"],width=10).grid(row=3,column=1,sticky="w");ttk.Entry(b,textvariable=self.v["titley"],width=10).grid(row=3,column=2,sticky="w")
        ttk.Label(b,text="X 轴标题位置 / 距离").grid(row=4,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v["xlabelpos"],values=["左侧","居中","右侧"],state="readonly",width=9).grid(row=4,column=1,sticky="w");ttk.Entry(b,textvariable=self.v["xlabelpad"],width=10).grid(row=4,column=2,sticky="w")
        ttk.Label(b,text="Y 轴标题位置 / 距离").grid(row=5,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v["ylabelpos"],values=["下方","居中","上方"],state="readonly",width=9).grid(row=5,column=1,sticky="w");ttk.Entry(b,textvariable=self.v["ylabelpad"],width=10).grid(row=5,column=2,sticky="w")
        for r,(lab,a,z) in enumerate([("X 范围","xmin","xmax"),("Y 范围","ymin","ymax")],6):ttk.Label(b,text=lab).grid(row=r,column=0,sticky="w");ttk.Entry(b,textvariable=self.v[a],width=10).grid(row=r,column=1,sticky="w");ttk.Entry(b,textvariable=self.v[z],width=10).grid(row=r,column=2,sticky="w")
        for r,(lab,a,z) in enumerate([("X 主 / 次刻度","xmajor","xminor"),("Y 主 / 次刻度","ymajor","yminor")],8):ttk.Label(b,text=lab).grid(row=r,column=0,sticky="w");ttk.Entry(b,textvariable=self.v[a],width=10).grid(row=r,column=1,sticky="w");ttk.Entry(b,textvariable=self.v[z],width=10).grid(row=r,column=2,sticky="w")
        ttk.Label(b,text="字体").grid(row=10,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v["font"],values=["Arial","Times New Roman","Calibri","Helvetica","Microsoft YaHei"],state="readonly",width=18).grid(row=10,column=1,columnspan=2,sticky="w")
        for r,(lab,k) in enumerate([("刻度数字字号","ticksize"),("标题字号","titlesize"),("轴标题字号","axissize")],11):ttk.Label(b,text=lab).grid(row=r,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v[k],values=sizes,state="readonly",width=8).grid(row=r,column=1,sticky="w")
        ttk.Checkbutton(b,text="标题加粗",variable=self.v["titlebold"],onvalue="1",offvalue="0").grid(row=12,column=2,sticky="w");ttk.Checkbutton(b,text="轴标题加粗",variable=self.v["axisbold"],onvalue="1",offvalue="0").grid(row=13,column=2,sticky="w")
        ttk.Label(b,text="图例位置").grid(row=14,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v["legend"],values=["自动（最佳位置）","右上","左上","右下","左下","图外右侧","自定义","隐藏"],state="readonly",width=18).grid(row=14,column=1,columnspan=2,sticky="w")
        ttk.Label(b,text="自定义图例 X / Y").grid(row=15,column=0,sticky="w");ttk.Entry(b,textvariable=self.v["legendx"],width=10).grid(row=15,column=1,sticky="w");ttk.Entry(b,textvariable=self.v["legendy"],width=10).grid(row=15,column=2,sticky="w")
        ttk.Label(b,text="宽 × 高 (cm)").grid(row=16,column=0,sticky="w");ttk.Entry(b,textvariable=self.v["w"],width=10).grid(row=16,column=1,sticky="w");ttk.Entry(b,textvariable=self.v["h"],width=10).grid(row=16,column=2,sticky="w");ttk.Label(b,text="DPI（保存时）").grid(row=17,column=0,sticky="w");ttk.Combobox(b,textvariable=self.v["dpi"],values=["150","300","450","600"],state="readonly",width=8).grid(row=17,column=1,sticky="w");ttk.Checkbutton(b,text="透明背景",variable=self.v["transparent"],onvalue="1",offvalue="0").grid(row=17,column=2,sticky="w")
        buttons=ttk.Frame(l);buttons.pack(pady=9);ttk.Button(buttons,text="刷新预览",command=lambda:self.render(True),width=14).pack(side="left",padx=3);ttk.Button(buttons,text="保存图片…",command=self.saveas,width=14).pack(side="left",padx=3)
        for variable in self.v.values():variable.trace_add("write",lambda *_:self.schedule())
    def add(self,path=None,color=None):
        x=Row(self.rowbox,self.delete,self.schedule);x.f.pack(fill="x",pady=3);self.rows.append(x)
        if path:x.set_file(path,color)
        self.after_idle(self.resize_curve_area);self.schedule();return x
    def resize_curve_area(self,_event=None):
        required=self.rowbox.winfo_reqheight();self.data_canvas.configure(scrollregion=self.data_canvas.bbox("all"),height=min(max(required,135),350))
    def batch_add(self):
        paths=filedialog.askopenfilenames(title="选择一个或多个 AKTA CSV",filetypes=[("CSV","*.csv"),("All files","*.*")])
        if not paths:return
        palette=["#1464F4","#E8251C","#2E9D45","#8A4FC4","#F08A24","#00A6A6","#7A5230","#D94F9D"]
        first=self.rows[0] if len(self.rows)==1 and not self.rows[0].path.get() else None
        for i,path in enumerate(paths):
            color=palette[i%len(palette)]
            if first:first.set_file(path,color);first=None
            else:self.add(path,color)
        self.schedule()
    def delete(self,x):
        if len(self.rows)>1:x.f.destroy();self.rows.remove(x);self.after_idle(self.resize_curve_area);self.schedule()
    def saveas(self):
        p=filedialog.asksaveasfilename(defaultextension=".png",filetypes=[("PNG","*.png"),("PDF","*.pdf"),("SVG","*.svg")])
        if not p:return
        if self.render(True):
            transparent=self.v["transparent"].get()=="1";self.fig.savefig(p,dpi=int(self.v["dpi"].get()),bbox_inches="tight",transparent=transparent,facecolor="none" if transparent else "white")
            self.title(f"SEC 曲线绘图工具 — 已保存 {Path(p).name}")
            messagebox.showinfo("保存成功",f"图片已保存到：\n{p}",parent=self)
    def schedule(self):
        if self.preview_job:self.after_cancel(self.preview_job)
        self.preview_job=self.after(450,lambda:self.render(False))
    def render(self,show_error=False):
        self.preview_job=None
        try:
            xmin,xmax,ymin,ymax=[val(self.v[k].get(),k) for k in ("xmin","xmax","ymin","ymax")]
            if (xmin is None)!=(xmax is None) or (ymin is None)!=(ymax is None):raise ValueError("每个坐标轴的最小值和最大值需同时填写，或都留空。")
            if (xmin is not None and xmin>=xmax) or (ymin is not None and ymin>=ymax):raise ValueError("坐标最小值必须小于最大值。")
            plt.rcParams.update({"font.family":self.v["font"].get(),"font.size":float(self.v["ticksize"].get())});fig,ax=plt.subplots(figsize=(float(self.v["w"].get())/2.54,float(self.v["h"].get())/2.54),dpi=max(110,self.screen_dpi),constrained_layout=True)
            for row in self.rows:
                p,label,c,wells,ranges=row.spec();x,y,b=read_akta(p);o=np.argsort(x);x,y=x[o],y[o];ax.plot(x,y,color=c,lw=2.6,label=label,zorder=3);base=min(0.,float(y.min()))
                for n in wells:
                    if n in b:s,e=b[n];fx=np.r_[s,x[(x>=s)&(x<=e)],e];ax.fill_between(fx,base,np.interp(fx,x,y),color=c,alpha=.45,linewidth=0,zorder=2)
                for s,e in ranges:
                    fx=np.r_[s,x[(x>=s)&(x<=e)],e];ax.fill_between(fx,base,np.interp(fx,x,y),color=c,alpha=.45,linewidth=0,zorder=2)
            titleweight="bold" if self.v["titlebold"].get()=="1" else "normal";axisweight="bold" if self.v["axisbold"].get()=="1" else "normal"
            tx,ty=val(self.v["titlex"].get(),"标题 X"),val(self.v["titley"].get(),"标题 Y");xpad=val(self.v["xlabelpad"].get(),"X 轴标题距离");ypad=val(self.v["ylabelpad"].get(),"Y 轴标题距离")
            if tx is None or ty is None or xpad is None or ypad is None:raise ValueError("标题位置和坐标轴标题距离不能为空。")
            xloc={"左侧":"left","居中":"center","右侧":"right"}[self.v["xlabelpos"].get()];yloc={"下方":"bottom","居中":"center","上方":"top"}[self.v["ylabelpos"].get()]
            ax.set_title(self.v["title"].get(),x=tx,y=ty,fontsize=float(self.v["titlesize"].get()),fontweight=titleweight);ax.set_xlabel(self.v["xlabel"].get(),loc=xloc,labelpad=xpad,fontsize=float(self.v["axissize"].get()),fontweight=axisweight);ax.set_ylabel(self.v["ylabel"].get(),loc=yloc,labelpad=ypad,fontsize=float(self.v["axissize"].get()),fontweight=axisweight)
            if xmin is not None:ax.set_xlim(xmin,xmax)
            if ymin is not None:ax.set_ylim(ymin,ymax)
            for key,axis in (("xmajor",ax.xaxis),("ymajor",ax.yaxis)):
                z=val(self.v[key].get(),key)
                if z:axis.set_major_locator(MultipleLocator(z))
            for key,axis in (("xminor",ax.xaxis),("yminor",ax.yaxis)):
                z=val(self.v[key].get(),key)
                if z:axis.set_minor_locator(MultipleLocator(z))
            transparent=self.v["transparent"].get()=="1";fig.patch.set_alpha(0 if transparent else 1);ax.set_facecolor("none" if transparent else "white");ax.spines[["top","right"]].set_visible(False);ax.tick_params(which="major",direction="out",length=6);ax.tick_params(which="minor",direction="out",length=3)
            locations={"自动（最佳位置）":"best","右上":"upper right","左上":"upper left","右下":"lower right","左下":"lower left"};position=self.v["legend"].get()
            if position!="隐藏":
                if position=="图外右侧":ax.legend(frameon=False,loc="center left",bbox_to_anchor=(1.02,.5))
                elif position=="自定义":
                    lx,ly=val(self.v["legendx"].get(),"图例 X"),val(self.v["legendy"].get(),"图例 Y")
                    if lx is None or ly is None:raise ValueError("自定义图例位置需要同时填写 X 和 Y（坐标轴比例，通常为 0–1）。")
                    ax.legend(frameon=False,loc="center",bbox_to_anchor=(lx,ly))
                else:ax.legend(frameon=False,loc=locations.get(position,"best"))
            if self.canvas:self.canvas.get_tk_widget().destroy();plt.close(self.fig)
            self.fig=fig;self.canvas=FigureCanvasTkAgg(fig,self.preview);self.canvas.draw();self.canvas.get_tk_widget().pack(fill="both",expand=True);return True
        except Exception as e:
            if show_error:messagebox.showerror("无法预览",str(e),parent=self)
            return False

if __name__=="__main__":enable_high_dpi();App().mainloop()
