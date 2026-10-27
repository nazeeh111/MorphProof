"""Figures from retained measurements. Requires matplotlib, not a runtime dependency."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'experiments/results-v1.json').read_text())['summary']+json.loads((root/'experiments/results-pool-v1.json').read_text())['summary']
methods=[('adaptive','#d84f24','o'),('no-feedback','#9f755f','x'),('pool-random','#236f61','s'),('boundary','#242923','D'),('random','#6086a4','^'),('uniform','#ada680','v'),('unit','#ae79a7','P'),('hypothesis','#6a69a6','*')]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#b4b8ae','text.color':'#242923','axes.labelcolor':'#242923','xtick.color':'#687068','ytick.color':'#687068','figure.facecolor':'#f5f3ec','axes.facecolor':'#fffefa','svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(12,5.8),sharey=True)
for ax,group,title in zip(axes,['synthetic','upstream'],['Authored behavioral differences','Two upstream naive-fold models']):
    for method,color,marker in methods:
        selected=sorted([r for r in rows if r['group']==group and r['method']==method],key=lambda r:r['budget'])
        ax.plot([r['budget'] for r in selected],[r['rate']*100 for r in selected],label=method,color=color,marker=marker,linewidth=2 if method in {'adaptive','boundary','pool-random'} else 1.15,linestyle='--' if method in {'adaptive','no-feedback'} else '-',markersize=5)
    ax.set_xscale('log',base=2);ax.set_xticks([8,32,128],['8','32','128']);ax.set_ylim(0,104);ax.set_yticks([0,25,50,75,100]);ax.set_xlabel('Candidate calls per trial');ax.set_title(title,loc='left',pad=13,fontweight='bold');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
axes[0].set_ylabel('Defect-seed trials detected (%)')
fig.suptitle('Adaptive selection has not established an advantage',x=.075,ha='left',fontsize=17,fontweight='bold',y=.98)
fig.text(.075,.905,'5 seeds · exact call budgets · 15 authored differences + 1 control · 2 independently selected upstream functions',fontsize=9,color='#687068')
handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=4,frameon=False,bbox_to_anchor=(.5,.055))
fig.text(.075,.025,'Rates are descriptive. Repeated seeds do not make independent defects. Full protocol and raw data: docs/technical-report.md',fontsize=8,color='#687068')
fig.subplots_adjust(top=.82,bottom=.26,left=.075,right=.98,wspace=.14)
fig.savefig(root/'docs/selector-evaluation.png',dpi=160);fig.savefig(root/'docs/selector-evaluation.svg')

p=root/'docs/selector-evaluation.svg'
p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
