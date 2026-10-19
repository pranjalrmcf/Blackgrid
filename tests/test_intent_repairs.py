"""Development regressions for inspected v1 failures and adjacent paraphrases."""
import pytest
from blackgrid.agent.inquiry import family
from blackgrid.agent.critic import validate_plan


@pytest.mark.parametrize('question,expected', [
    ('Are the clusters more pronounced than expected just from how many contacts each person has?', 'community'),
    ('Does clustering exceed a random baseline that preserves contact counts?', 'community'),
    ('Which nodes have the highest degree within the communities?', 'centrality'),
    ('Which nodes bridge clusters compared with random structure?', 'bridge'),
    ('Which pairs will message next and what is the uncertainty of that ranking?', 'forecast'),
    ('Review the saved synthetic posterior beliefs.', 'research'),
    ('Are the saved synthetic uncertainty estimates calibrated?', 'research'),
    ('Give the odds that this pair will message tomorrow.', 'clarify'),
    ('Can the synthetic posterior assign a probability to this network having communities?', 'clarify'),
])
def test_target_preserved_across_paraphrases(question, expected):
    assert family(question, {'family':'auto'}) == expected


@pytest.mark.parametrize('forced_family', ['auto','community','research','forecast'])
def test_scope_boundary_cannot_be_overridden_by_a_family(forced_family):
    decision = validate_plan('Give a calibrated probability that a pair will message tomorrow.',
        {'family':forced_family}, {'decision':'run','tool_calls':[{'tool':'belief_update','args':{}}]})
    assert not decision.allowed and not decision.tool_calls
    assert 'uncalibrated scores' in decision.reasons[0]


def test_refusal_explanation_is_preserved_as_unverified_model_text():
    decision = validate_plan('Predict new connections.', {'family':'auto'},
        {'decision':'refuse','reason':'I cannot use future messages or the held-out answer key.'})
    assert not decision.allowed
    assert 'Planner explanation (unverified)' in decision.reasons[0]
    assert 'future messages' in decision.reasons[0]
