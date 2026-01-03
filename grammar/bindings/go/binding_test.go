package tree_sitter_tahta_test

import (
	"testing"

	tree_sitter "github.com/smacker/go-tree-sitter"
	"github.com/tree-sitter/tree-sitter-tahta"
)

func TestCanLoadGrammar(t *testing.T) {
	language := tree_sitter.NewLanguage(tree_sitter_tahta.Language())
	if language == nil {
		t.Errorf("Error loading Tahta grammar")
	}
}
