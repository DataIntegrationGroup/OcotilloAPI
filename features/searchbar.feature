Feature: Unified search bar with autosuggestions
  As a user of Ocotillo, the bureau's data management tool
  I want a unified search bar at the top of the page
  So that I can quickly find relevant data based on my input and search history

  Background:
    Given I am logged in as a user
    And I am on the main page of Ocotillo

  # ---- Core behavior ----

  Scenario: Display search suggestions ordered by relevance
    When I type "Rio" into the search bar
    Then the first suggestions should be from my recent searches containing "Rio"
    And the next suggestions should be from the app’s overall recent searches containing "Rio"
    And the final suggestions should be any other possible matches containing "Rio"

  Scenario: Accept an autosuggestion with TAB
    Given I have started typing "aqu"
    And an autosuggestion "aquifer levels" is displayed
    When I press the TAB key
    Then the search input should be replaced with "aquifer levels"
    And I should be able to submit the search immediately

  Scenario: Show most likely search based on user history
    Given I previously searched for "water rights"
    When I type "wat" into the search bar
    Then "water rights" should be the top suggestion

  Scenario: Show app-wide recent searches when user has no history
    Given I have no recent search history
    When I type "salinity"
    Then the top suggestion should come from overall recent searches containing "salinity"

  Scenario: Show fallback matches when no history exists
    Given no user or app-wide recent searches match "xyz"
    When I type "xyz"
    Then the autosuggestions should include other possible matches containing "xyz"

  Scenario: No suggestions for empty input
    When I focus on the search bar without typing
    Then no autosuggestions should be displayed

  Scenario: Navigating suggestions with keyboard
    Given multiple autosuggestions are displayed
    When I press the DOWN arrow key
    Then the highlighted suggestion should change to the next in the list
    When I press the UP arrow key
    Then the highlighted suggestion should change to the previous in the list

  # ---- Edge & error cases ----

  Scenario: TAB pressed when no suggestions are visible
    Given no autosuggestions are displayed
    And the search input contains "aq"
    When I press the TAB key
    Then the search input should remain "aq"
    And no search should be submitted

  Scenario: TAB accepts the currently highlighted suggestion
    Given multiple autosuggestions are displayed
    And "aquifer recharge" is highlighted
    When I press the TAB key
    Then the search input should be replaced with "aquifer recharge"

  Scenario: TAB accepts the first suggestion when none is highlighted
    Given multiple autosuggestions are displayed
    And no suggestion is highlighted
    When I press the TAB key
    Then the search input should be replaced with the first suggestion in the list

  Scenario: Pressing Enter submits highlighted suggestion
    Given multiple autosuggestions are displayed
    And "Rio Grande wells" is highlighted
    When I press Enter
    Then a search should be submitted for "Rio Grande wells"

  Scenario: Pressing Enter with no highlighted suggestion submits typed text
    Given multiple autosuggestions are displayed
    And the search input contains "chemistry"
    And no suggestion is highlighted
    When I press Enter
    Then a search should be submitted for "chemistry"

  Scenario: Dismiss suggestions with Escape
    Given autosuggestions are displayed
    When I press Escape
    Then the autosuggestions panel should close
    And the typed input should remain unchanged

  Scenario: Click to select a suggestion
    Given autosuggestions are displayed
    When I click on "aquifer levels"
    Then the search input should be replaced with "aquifer levels"
    And a search should be ready to submit

  Scenario: Suggestions loading indicator and debouncing
    When I rapidly type "a", "aq", "aqu" into the search bar
    Then I should see a loading indicator while suggestions are fetched
    And the system should debounce requests to avoid sending one request per keystroke
    And only the latest input "aqu" should be used to fetch suggestions

  Scenario: Suggestions request times out
    Given the suggestions service is slow or unresponsive
    When I type "Rio"
    Then I should see a timeout message or fallback state
    And previously cached suggestions for "Rio" should be shown if available
    And the UI should not freeze

  Scenario: Search service temporarily unavailable
    Given the search service is unavailable
    When I type "nitrate"
    Then I should see an error message indicating suggestions are unavailable
    And the input should remain editable
    And I should still be able to submit a direct search for "nitrate"

  Scenario: Permission-filtered suggestions
    Given my account does not have access to certain datasets
    When autosuggestions are displayed for "rights"
    Then suggestions requiring permissions I lack should be excluded
    And only accessible suggestions should be shown

  Scenario: Case-insensitive and diacritic-insensitive matching
    When I type "rio grande"
    Then suggestions containing "Rio Grande" with any case or diacritic variations should be matched and ordered as specified

  Scenario: Preserve ordering when paging suggestions
    Given more suggestions exist than can be shown at once
    When I scroll the suggestion list
    Then additional suggestions should load without changing the relative ordering
    And user-history suggestions should not appear after global or other matches

  Scenario: Keyboard focus management and accessibility
    Given autosuggestions are displayed
    When I navigate with the keyboard
    Then focus should remain within the suggestions list until dismissed or accepted
    And the suggestions list should expose roles and labels for assistive technologies
