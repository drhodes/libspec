from libspec import Feature

#
# https://github.com/github/spec-kit/blob/main/templates/spec-template.md
#

class UserStory(Feature):
    '''
    User Story - {brief-title} (Priority: {priority})

    {user-journey}

    Why this priority: {explanation}

    Independent Test: [Describe how this can be tested independently -
    e.g., "Can be fully tested by [specific action] and delivers
    [specific value]"]

    Acceptance Scenarios:

    Given [initial state], When [action], Then [expected outcome]
    Given [initial state], When [action], Then [expected outcome]
    '''
            
