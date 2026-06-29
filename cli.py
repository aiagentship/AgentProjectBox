"""AgentProjectBox CLI - Command-line interface."""

import json
import sys
from datetime import datetime
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from agentprojectbox import Orchestrator
from shared.models import ProjectStatus


console = Console()

# Global orchestrator
orchestrator: Orchestrator | None = None


def get_orchestrator(swarm_mode: bool = False) -> Orchestrator:
    """Get or create orchestrator instance."""
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator(swarm_mode=swarm_mode)
    return orchestrator


@click.group()
@click.option('--swarm', is_flag=True, help='Enable swarm mode for multi-project coordination')
@click.option('--output', type=click.Choice(['json', 'cli']), default='cli', help='Output format')
@click.pass_context
def cli(ctx, swarm, output):
    """AgentProjectBox - Headless project management for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj['swarm_mode'] = swarm
    ctx.obj['output_format'] = output
    ctx.obj['orchestrator'] = get_orchestrator(swarm_mode=swarm)


# -----------------------------------------------------------------------------
# Project Commands
# -----------------------------------------------------------------------------

@cli.group()
def project():
    """Project management commands."""
    pass


@project.command(name='create')
@click.argument('title')
@click.option('--description', '-d', help='Project description')
@click.option('--request', '-r', help='Natural language project request')
@click.option('--due-date', help='Due date (YYYY-MM-DD)')
@click.option('--budget', '-b', type=float, help='Budget amount')
@click.option('--objectives', '-o', multiple=True, help='Project objectives')
@click.pass_context
def create_project(ctx, title, description, request, due_date, budget, objectives):
    """Create a new project."""
    orch = ctx.obj['orchestrator']
    
    kwargs = {}
    if description:
        kwargs['description'] = description
    if due_date:
        kwargs['due_date'] = datetime.fromisoformat(due_date)
    
    project, result_context = orch.create_project(
        title=title,
        request_text=request,
        objectives=list(objectives) if objectives else None,
        **kwargs
    )
    
    if project is None:
        # Need clarification
        console.print(f"[yellow]Project request needs clarification:[/yellow]")
        for q in result_context.get('questions', []):
            console.print(f"  • {q}")
        return
    
    if budget:
        orch.set_project_budget(project.id, budget)
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps(result_context, indent=2))
    else:
        console.print(Panel(f"[green]Created project:[/green] {project.title}", 
                           subtitle=f"ID: {project.id}"))
        console.print(f"Objectives: {len(project.objectives)}")
        console.print(f"Deliverables: {len(project.deliverables)}")
        console.print(f"Auto-generated tasks: {len(project.tasks)}")


@project.command(name='list')
@click.option('--status', type=click.Choice(['draft', 'active', 'paused', 'completed']), 
              help='Filter by status')
@click.pass_context
def list_projects(ctx, status):
    """List all projects."""
    orch = ctx.obj['orchestrator']
    projects = orch.list_projects(status=status)
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps([p.model_dump() for p in projects], indent=2, default=str))
    else:
        table = Table(title="Projects")
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Title")
        table.add_column("Status", style="bold")
        table.add_column("Progress")
        table.add_column("Due Date")
        
        for p in projects:
            progress = f"{p.calculate_progress():.0%}" if p.tasks else "N/A"
            due = p.timeline.due_date.strftime('%Y-%m-%d') if p.timeline else "Not set"
            
            status_style = {
                'draft': 'dim',
                'active': 'green',
                'paused': 'yellow',
                'completed': 'blue',
                'cancelled': 'red',
            }.get(p.status.value, 'white')
            
            table.add_row(
                p.id[:8], 
                p.title[:40], 
                f"[{status_style}]{p.status.value}[/{status_style}]",
                progress,
                due,
            )
        
        console.print(table)


@project.command(name='show')
@click.argument('project_id')
@click.pass_context
def show_project(ctx, project_id):
    """Show project details."""
    orch = ctx.obj['orchestrator']
    project = orch.get_project(project_id)
    
    if not project:
        console.print(f"[red]Project {project_id} not found[/red]")
        return
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps(orch.export_project(project_id, 'json'), indent=2, default=str))
    else:
        console.print(orchestrator.output.format_cli_project(project))


@project.command(name='delete')
@click.argument('project_id')
@click.confirmation_option(prompt='Are you sure you want to delete this project?')
@click.pass_context
def delete_project(ctx, project_id):
    """Delete a project."""
    orch = ctx.obj['orchestrator']
    
    if project_id in orch.projects:
        del orch.projects[project_id]
        console.print(f"[green]Deleted project {project_id}[/green]")
    else:
        console.print(f"[red]Project {project_id} not found[/red]")


# -----------------------------------------------------------------------------
# Task Commands
# -----------------------------------------------------------------------------

@cli.group()
def task():
    """Task management commands."""
    pass


@task.command(name='add')
@click.argument('project_id')
@click.argument('title')
@click.option('--depends', '-d', multiple=True, help='Task IDs this depends on')
@click.option('--hours', '-h', type=float, default=8.0, help='Estimated hours')
@click.option('--priority', '-p', type=click.Choice(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']), 
              default='MEDIUM', help='Task priority')
@click.pass_context
def add_task(ctx, project_id, title, depends, hours, priority):
    """Add a task to a project."""
    orch = ctx.obj['orchestrator']
    
    try:
        task = orch.add_task(
            project_id=project_id,
            title=title,
            depends_on=list(depends) if depends else None,
            estimated_hours=hours,
            priority=priority,
        )
        
        if ctx.obj['output_format'] == 'json':
            click.echo(json.dumps(task.model_dump(), indent=2, default=str))
        else:
            console.print(f"[green]Added task:[/green] {task.title} (ID: {task.id[:8]})")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@task.command(name='list')
@click.argument('project_id')
@click.option('--status', type=click.Choice(['pending', 'blocked', 'in-progress', 'completed']),
              help='Filter by status')
@click.pass_context
def list_tasks(ctx, project_id, status):
    """List tasks in a project."""
    orch = ctx.obj['orchestrator']
    project = orch.get_project(project_id)
    
    if not project:
        console.print(f"[red]Project {project_id} not found[/red]")
        return
    
    tasks = project.tasks
    if status:
        tasks = [t for t in tasks if t.status.value == status]
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps([t.model_dump() for t in tasks], indent=2, default=str))
    else:
        console.print(f"[bold]Tasks for {project.title}:[/bold]")
        console.print(orch.output.format_cli_tasks(tasks))


@task.command(name='update')
@click.argument('project_id')
@click.argument('task_id')
@click.argument('status', type=click.Choice(['pending', 'blocked', 'in-progress', 'review', 'completed']))
@click.pass_context
def update_task(ctx, project_id, task_id, status):
    """Update task status."""
    orch = ctx.obj['orchestrator']
    
    try:
        task = orch.update_task_status(project_id, task_id, status)
        console.print(f"[green]Updated task {task.title} to {status}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


# -----------------------------------------------------------------------------
# Agent Commands
# -----------------------------------------------------------------------------

@cli.group()
def agent():
    """Agent management commands."""
    pass


@agent.command(name='register')
@click.argument('name')
@click.option('--capabilities', '-c', multiple=True, 
              help='Agent capabilities (e.g., code_generation, testing)')
@click.pass_context
def register_agent(ctx, name, capabilities):
    """Register a new agent."""
    orch = ctx.obj['orchestrator']
    
    agent = orch.register_agent(
        name=name,
        capabilities=list(capabilities) if capabilities else None,
    )
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps(agent.model_dump(), indent=2, default=str))
    else:
        console.print(f"[green]Registered agent:[/green] {agent.name} (ID: {agent.id[:8]})")


@agent.command(name='list')
@click.pass_context
def list_agents(ctx):
    """List all registered agents."""
    orch = ctx.obj['orchestrator']
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps({id: a.model_dump() for id, a in orch.agents.items()}, 
                              indent=2, default=str))
    else:
        table = Table(title="Agents")
        table.add_column("ID", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Type")
        table.add_column("Capacity")
        table.add_column("Capabilities")
        
        for agent in orch.agents.values():
            caps = ", ".join(c.value for c in agent.capabilities[:3])
            if len(agent.capabilities) > 3:
                caps += f" (+{len(agent.capabilities) - 3})"
            
            table.add_row(
                agent.id[:8],
                agent.name,
                agent.type,
                f"{agent.current_task_count}/{agent.max_concurrent_tasks}",
                caps,
            )
        
        console.print(table)


@agent.command(name='join')
@click.argument('agent_id')
@click.argument('project_id')
@click.pass_context
def agent_join(ctx, agent_id, project_id):
    "" "Agent joins a project." ""
    orch = ctx.obj['orchestrator']
    
    try:
        result = orch.agent_join_project(agent_id, project_id)
        console.print(f"[green]Agent joined project:[/green] {result}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@agent.command(name='claim')
@click.argument('agent_id')
@click.argument('project_id')
@click.argument('task_id')
@click.pass_context
def claim_task(ctx, agent_id, project_id, task_id):
    """Agent claims a task."""
    orch = ctx.obj['orchestrator']
    
    try:
        result = orch.claim_task(agent_id, project_id, task_id)
        if result.get('success'):
            console.print(f"[green]Task claimed successfully[/green]")
            if result.get('method') == 'arbitration':
                console.print(f"[dim]Decision: {result.get('decision', {}).get('reason')}[/dim]")
        else:
            console.print(f"[yellow]Task claim unsuccessful: {result.get('decision', {}).get('reason')}[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


# -----------------------------------------------------------------------------
# Monitor Commands
# -----------------------------------------------------------------------------

@cli.group()
def monitor():
    """Monitoring and analysis commands."""
    pass


@monitor.command(name='analyze')
@click.argument('project_id')
@click.pass_context
def monitor_analyze(ctx, project_id):
    """Run full analysis on a project."""
    orch = ctx.obj['orchestrator']
    
    try:
        analysis = orch.monitor_project(project_id)
        
        if ctx.obj['output_format'] == 'json':
            click.echo(json.dumps(analysis, indent=2, default=str))
        else:
            console.print(f"[bold]Project Analysis: {project_id}[/bold]\n")
            
            if 'forecast' in analysis:
                forecast = analysis['forecast']
                prob = forecast.get('probability_on_time', 0)
                prob_color = 'green' if prob > 0.7 else 'yellow' if prob > 0.4 else 'red'
                console.print(f"On-time probability: [{prob_color}]{prob:.0%}[/{prob_color}]")
                
                if 'expected_completion' in forecast:
                    console.print(f"Expected completion: {forecast['expected_completion']}")
            
            if 'risks' in analysis:
                console.print(f"\n[yellow]Identified Risks ({len(analysis['risks'])}):[/yellow]")
                for risk in analysis['risks'][:5]:
                    console.print(f"  • {risk['description'][:60]}...")
            
            if 'alerts' in analysis:
                console.print(orch.output.format_cli_alerts([type('Alert', (), a)() for a in analysis['alerts']]))
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@monitor.command(name='forecast')
@click.argument('project_id')
@click.pass_context
def monitor_forecast(ctx, project_id):
    """Show forecast for a project."""
    orch = ctx.obj['orchestrator']
    
    try:
        forecast = orch.forecast(project_id)
        click.echo(json.dumps(forecast, indent=2, default=str))
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@monitor.command(name='alerts')
@click.option('--project', '-p', help='Filter by project ID')
@click.pass_context
def monitor_alerts(ctx, project):
    """Show active alerts."""
    orch = ctx.obj['orchestrator']
    
    alerts = orch.check_alerts(project_id=project)
    
    if ctx.obj['output_format'] == 'json':
        click.echo(json.dumps([a.model_dump() for a in alerts], indent=2, default=str))
    else:
        console.print(orch.output.format_cli_alerts(alerts))


# -----------------------------------------------------------------------------
# Resource Commands
# -----------------------------------------------------------------------------

@cli.group()
def resource():
    """Resource allocation commands."""
    pass


@resource.command(name='allocate')
@click.argument('project_id')
@click.option('--task', '-t', help='Specific task ID to allocate')
@click.pass_context
def allocate_resources(ctx, project_id, task):
    """Allocate resources for tasks."""
    orch = ctx.obj['orchestrator']
    
    try:
        recommendations = orch.allocate_task_resources(project_id, task)
        
        if ctx.obj['output_format'] == 'json':
            click.echo(json.dumps([r if isinstance(r, dict) else r.__dict__ for r in recommendations], 
                                  indent=2, default=str))
        else:
            if recommendations:
                console.print(f"[green]Allocated {len(recommendations)} tasks:[/green]")
                for rec in recommendations:
                    console.print(f"  • {rec.task_id} → {rec.recommended_agents[0][0] if rec.recommended_agents else 'None'} "
                                 f"(confidence: {rec.confidence:.2f})")
            else:
                console.print("[yellow]No tasks to allocate[/yellow]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@resource.command(name='swarm')
@click.argument('project_ids', nargs=-1, required=True)
@click.pass_context
def activate_swarm(ctx, project_ids):
    """Activate swarm mode for multiple projects."""
    orch = ctx.obj['orchestrator']
    
    result = orch.join_swarm(list(project_ids))
    click.echo(json.dumps(result, indent=2))


# -----------------------------------------------------------------------------
# Finance Commands
# -----------------------------------------------------------------------------

@cli.group()
def finance():
    """Finance and budget commands."""
    pass


@finance.command(name='budget')
@click.argument('project_id')
@click.argument('amount', type=float)
@click.pass_context
def set_budget(ctx, project_id, amount):
    """Set project budget."""
    orch = ctx.obj['orchestrator']
    
    try:
        budget = orch.set_project_budget(project_id, amount)
        console.print(f"[green]Set budget: ${amount:,.2f} for project {project_id[:8]}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@finance.command(name='show')
@click.argument('project_id')
@click.pass_context
def show_finance(ctx, project_id):
    """Show project finance."""
    orch = ctx.obj['orchestrator']
    
    finance_data = orch.get_project_finance(project_id)
    click.echo(json.dumps(finance_data, indent=2))


@finance.command(name='set-rate')
@click.argument('agent_id')
@click.argument('rate', type=float)
@click.pass_context
def set_agent_rate(ctx, agent_id, rate):
    """Set agent hourly rate."""
    orch = ctx.obj['orchestrator']
    
    try:
        orch.set_agent_rate(agent_id, rate)
        console.print(f"[green]Set rate: ${rate}/hour for agent {agent_id[:8]}[/green]")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


# -----------------------------------------------------------------------------
# Export Commands
# -----------------------------------------------------------------------------

@cli.group()
def export():
    """Export commands."""
    pass


@export.command(name='json')
@click.argument('project_id')
@click.option('--full', is_flag=True, help='Export full data')
@click.pass_context
def export_json(ctx, project_id, full):
    """Export project as JSON."""
    orch = ctx.obj['orchestrator']
    
    try:
        data = orch.output.export_project_json(
            orch.get_project(project_id),
            include_full_data=full,
        )
        click.echo(json.dumps(data, indent=2, default=str))
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@export.command(name='report')
@click.argument('project_id')
@click.pass_context
def export_report(ctx, project_id):
    """Export comprehensive report."""
    orch = ctx.obj['orchestrator']
    
    try:
        report = orch.export_full_report(project_id)
        click.echo(json.dumps(report, indent=2, default=str))
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")


@export.command(name='compliance')
@click.argument('project_id')
@click.pass_context
def export_compliance(ctx, project_id):
    """Export compliance report."""
    orch = ctx.obj['orchestrator']
    
    report = orch.generate_compliance_report(project_id)
    click.echo(json.dumps(report, indent=2))


# -----------------------------------------------------------------------------
# System Commands
# -----------------------------------------------------------------------------

@cli.command(name='status')
@click.pass_context
def system_status(ctx):
    """Show system status."""
    orch = ctx.obj['orchestrator']
    
    health = orch.get_health_summary()
    console.print(Panel.fit(
        f"Projects: {health['projects']}\n"
        f"Agents: {health['agents']}\n"
        f"Swarm Mode: {'enabled' if health['swarm_mode'] else 'disabled'}\n"
        f"Audit Events: {health['audit_events']}",
        title="AgentProjectBox Status"
    ))


@cli.command(name='config')
def show_config():
    """Show current configuration."""
    from shared.config import config
    click.echo(json.dumps(config.to_dict(), indent=2))


def main():
    """Entry point for CLI."""
    cli()


if __name__ == '__main__':
    main()
