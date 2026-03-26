package tree_sitter_taht_test

import (
	"testing"

	tree_sitter "github.com/smacker/go-tree-sitter"
	"github.com/tree-sitter/tree-sitter-taht"
)

func TestCanLoadGrammar(t *testing.T) {
	language := tree_sitter.NewLanguage(tree_sitter_taht.Language())
	if language == nil {
		t.Errorf("Error loading Tahta grammar")
	}
}
