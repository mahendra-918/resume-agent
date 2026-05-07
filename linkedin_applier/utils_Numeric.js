const fs = require('fs');
const natural = require('natural');
const { TfIdf, WordTokenizer, PorterStemmer } = natural;
const readline = require('readline');

const answersFilePath = './numeric_response.json';
let answersDatabase = {};

if (fs.existsSync(answersFilePath)) {
  const data = fs.readFileSync(answersFilePath, 'utf8');
  answersDatabase = JSON.parse(data);
} else {
  console.log('numeric_response.json not found. Creating a new one.');
  fs.writeFileSync(answersFilePath, JSON.stringify(answersDatabase, null, 2));
}

const keywords = [
  "javascript", "typescript", "node.js", "react.js", "angular", "vue.js",
  "python", "django", "flask",
  "java", "spring", "spring boot",
  "aws", "azure", "google cloud", "cloud computing",
  "docker", "kubernetes", "containerization",
  "sql", "nosql", "mongodb", "postgresql", "mysql", "Databases",
  "git", "github", "gitlab",
  "agile", "scrum", "kanban",
  "machine learning", "deep learning", "artificial intelligence", "data science",
  "html", "css", "sass", "bootstrap", "Web Development",
  "restful api", "graphql",
  "microservices", "serverless",
  "devops", "continuous integration", "continuous deployment",
  "software engineering", "software development", "full stack",
  "cybersecurity", "network security",
  "react native", "mobile development",
  "blockchain", "ethereum", "smart contracts",
  "agile methodologies", "lean methodologies",
  "big data", "apache spark", "hadoop",
  "C++", "C", "Kotlin",
  "software testing", "teamcenter", "dita xml"
];

function normalizeAndTokenize(text) {
  const regex = /^(how many years of work experience do you have with|how many years of do you have with|how many years of do you have)/i;
  const processedText = text.replace(regex, '');
  const tokenizer = new WordTokenizer();
  const tokens = tokenizer.tokenize(processedText.toLowerCase());
  return tokens.map(token => PorterStemmer.stem(token)).join(' ');
}

function saveAnswer(question, answer) {
  answersDatabase[question] = answer;
  fs.writeFileSync(answersFilePath, JSON.stringify(answersDatabase, null, 2), 'utf8');
}

async function handleNewQuestion(question) {
  console.log(`No sufficiently similar question found for: "${question}". Please provide an answer.`);
  const answer = await new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });
    rl.question(`Answer for "${question}": `, (input) => {
      rl.close();
      resolve(input.trim());
    });
  });

  saveAnswer(question, answer);
  return answer;
}

function calculateSimilarity(question1, question2) {
  const tfidf = new TfIdf();
  tfidf.addDocument(normalizeAndTokenize(question1));
  tfidf.addDocument(normalizeAndTokenize(question2));

  let similarity = 0;
  tfidf.listTerms(0).forEach(function(item) {
    const term = item.term;
    const tfidf1 = tfidf.tfidf(term, 0);
    const tfidf2 = tfidf.tfidf(term, 1);
    similarity += tfidf1 * tfidf2;
  });

  return similarity;
}

function getMostSimilarQuestion(question) {
  const questions = Object.keys(answersDatabase);
  if (questions.length === 0) return null;

  if (answersDatabase.hasOwnProperty(question)) {
    return { mostSimilarQuestion: question, maxSimilarity: 1.0 };
  }

  let mostSimilarQuestion = null;
  let maxSimilarity = -1;

  for (const q of questions) {
    const dbContainsKeyword = keywords.some(keyword => q.toLowerCase().includes(keyword));

    if (dbContainsKeyword) {
      let similarity = calculateSimilarity(question, q);
      const inputContainsKeyword = keywords.some(keyword => question.toLowerCase().includes(keyword));
      if (inputContainsKeyword) {
        similarity *= 1.2;
      }
      if (similarity > maxSimilarity) {
        maxSimilarity = similarity;
        mostSimilarQuestion = q;
      }
    }
  }

  if (!mostSimilarQuestion) {
    for (const q of questions) {
      if (!keywords.some(keyword => q.toLowerCase().includes(keyword))) {
        let similarity = calculateSimilarity(question, q);
        if (similarity > maxSimilarity) {
          maxSimilarity = similarity;
          mostSimilarQuestion = q;
        }
      }
    }
  }

  if (maxSimilarity < 0.4) {
    return null;
  }

  return { mostSimilarQuestion, maxSimilarity };
}

module.exports = {
  answersDatabase,
  saveAnswer,
  handleNewQuestion,
  calculateSimilarity,
  getMostSimilarQuestion,
  normalizeAndTokenize
};
