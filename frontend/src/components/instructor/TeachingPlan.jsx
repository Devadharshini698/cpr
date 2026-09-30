import React from 'react';

export default function TeachingPlan({plan}) {
  if (!plan) return null;
  return <details style={{padding:12,marginBottom:16,border:'1px solid #64748b',borderRadius:8}}>
    <summary style={{cursor:'pointer',fontWeight:700}}>Faculty teaching plan — {plan.title}</summary>
    <p>{plan.delivery}</p><p><strong>Clinical focus:</strong> {plan.clinical_focus}</p>
    <ul>{plan.objectives.map((item,i)=><li key={i}>{item}</li>)}</ul>
    <h4>Selected healthcare roles</h4><p>{plan.roster_note}</p>
    {plan.team_tasks.map(task=><p key={task.role}><strong>{task.label}:</strong> {task.expectation}</p>)}
    <h4>Expertise and escalation</h4>
    <ul>{plan.escalation.map((item,i)=><li key={i}>{item}</li>)}</ul>
    {plan.faculty_challenges.length>0 && <><h4>Manual faculty challenges</h4>
      {plan.faculty_challenges.map((item,i)=><div key={i}><strong>{i+1}. {item.trigger}</strong><p>{item.prompt}</p><p><em>Observe:</em> {item.expected}</p></div>)}
    </>}
    <p>{plan.scope}</p><p>{plan.progression}</p>
  </details>;
}
