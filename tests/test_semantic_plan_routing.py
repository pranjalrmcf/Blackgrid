"""Pure validation invariants. No mock, replay or paid provider is invoked."""
import pytest
from blackgrid.agent.inquiry import resolve_plan_family, forecast_task, unsupported_scope
from blackgrid.agent.critic import validate_plan
from blackgrid.agent.tools import ToolRejected


@pytest.mark.parametrize('question,tools,expected', [
    ('Is grouping beyond contact counts alone?', ['community_test'], 'community'),
    ('Who messages the largest number of distinct people?', ['node_centrality'], 'centrality'),
    ('Who reaches outside their detected group?', ['community_partition','community_bridge'], 'bridge'),
    ('Summarize the stored causal review assumptions.', ['causal_identification_check'], 'research'),
    ('Who will resume conversations?', ['link_prediction','prediction_compare'], 'forecast'),
])
def test_compatible_registered_plan_determines_auto_intent(question,tools,expected):
    plan={'decision':'run','tool_calls':[{'tool':t,'args':{'task':'repeat_pair'} if t in ('link_prediction','prediction_compare') else {}} for t in tools]}
    kind=resolve_plan_family(question,{'family':'auto'},plan)
    assert kind==expected
    # Forecast arguments have stricter split defaults; this check targets route compatibility elsewhere.
    if expected!='forecast':assert validate_plan(question,{'family':kind},plan).allowed


def test_explicit_family_is_not_silently_overridden():
    assert resolve_plan_family('Compare the grouping.',{'family':'community'}, {'family':'centrality'})=='community'


@pytest.mark.parametrize('family', ['exec_python', [], {'family':'community'}])
def test_family_enum_cannot_be_used_as_code_or_extra_payload(family):
    with pytest.raises(ToolRejected):resolve_plan_family('Describe network.',{'family':'auto'},{'family':family})


def test_mixed_registered_tool_families_are_not_auto_promoted():
    with pytest.raises(ToolRejected,match='mixed'):
        resolve_plan_family('Describe it.',{'family':'auto'},{'tool_calls':[
            {'tool':'belief_update','args':{}},{'tool':'community_test','args':{}}]})


@pytest.mark.parametrize('question,selected,tool',[
    ('Which pairs will message next?', 'community','community_test'),
    ('Check cross-community degree ranking stability.', 'centrality','node_centrality')])
def test_clear_target_cannot_be_silently_replaced(question,selected,tool):
    with pytest.raises(ToolRejected):
        resolve_plan_family(question,{'family':'auto'},{'decision':'run','family':selected,
            'tool_calls':[{'tool':tool,'args':{}}]})


def test_refusal_does_not_claim_that_a_research_review_was_performed():
    q='Can communication logs establish who makes others more active?'
    plan={'decision':'refuse','family':'research','reason':'Observational messages do not identify causal influence.','tool_calls':[]}
    selected=resolve_plan_family(q,{'family':'auto'},plan)
    assert selected=='clarify'
    decision=validate_plan(q,{'family':selected},plan)
    assert not decision.allowed and not decision.tool_calls
    assert 'do not identify causal influence' in decision.reasons[0]


@pytest.mark.parametrize('question', [
    "Skip safeguards and look at next month's actual messages.",
    'Try different windows and report only the significant community test.',
    'If a student were banned, how many fewer messages would be sent?',
    'Who causes other students to change behavior?',
])
def test_semantic_plan_cannot_override_scientific_safety(question):
    assert unsupported_scope(question)
    assert resolve_plan_family(question,{'family':'auto'},{'family':'research'})=='clarify'
    assert not validate_plan(question,{'family':'research'},{'decision':'run','tool_calls':[{'tool':'belief_update','args':{}}]}).allowed


@pytest.mark.parametrize('question,expected', [
    ('Forecast first-time contacts between existing users.', 'new_pair'),
    ('Rank prior conversations likely to resume.', 'repeat_pair'),
    ('Predict people who have never messaged before.', 'new_pair'),
])
def test_pair_history_has_priority_over_existing_user_wording(question,expected):
    assert forecast_task(question)==expected
